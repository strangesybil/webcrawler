import requests
from bs4 import BeautifulSoup
from queue import PriorityQueue
from collections import defaultdict
from urllib.parse import urljoin, urlparse
from math import log2
import tldextract

#Initialize the queue
pq= PriorityQueue(maxsize=100) #The queue of URLs to crawl
visited_domains=set()#set of domains that have been visited
superdomain_count=defaultdict(int) #How many times have I seen this superdomain?
superdomain_subdomains=defaultdict(set) #set of subdomains for each superdomain
search_query=input("What are you looking for? ")
seed_url = ["https://bing.com/search"]


#Get initial search results from Bing
for url in seed_url:
    response = requests.get(
        url,
        params={"q": search_query},
    )

    print("Seed page status:", response.status_code)

#Download pages in html 
    with open(f"/Users/rae/Documents/source.html", "w",encoding="utf-8") as f:
        f.write(response.text)

#Use BeautifulSoup library to parse initial search results and extract links
    soup = BeautifulSoup(response.text, "html.parser")

    for link in soup.find_all("a",href=True):
       url=link["href"]
       if url.startswith("http"):
           hostname=urlparse(url).netloc
           result=tldextract.extract(hostname)
           superdomain=result.registered_domain
           superdomain_count[superdomain]+=1
           p = superdomain_count[superdomain]
           s = len(superdomain_subdomains[superdomain])
           combined_score=1/log2(p+2)+1/log2(s+2)
           priority=-combined_score #negate so it's popped first?
           pq.put((priority,url))
           print(f"\nHow many items are in the queue? {pq.qsize()}")
    
while not pq.empty():
    priority,url = pq.get()
    hostname = urlparse(url).netloc
    result=tldextract.extract(hostname)
    superdomain=result.registered_domain
    if superdomain in visited_domains:
        continue
    visited_domains.add(superdomain)
    #Try to download pages in html
    try: 
        response=requests.get(url,timeout=10)
        with open(f"/Users/rae/Documents/source1.html", "w",encoding="utf-8") as f:
                    f.write(response.text)
    except requests.exceptions.RequestException as e:
            print("Request failed:", e)
            continue
            #Only count successful responses (status code 200) for scoring
    if response.status_code != 200:
                print("Failed.")
                continue 

    #Successful visit and download
    hostname=urlparse(url).netloc
    result=tldextract.extract(hostname)
    superdomain=result.registered_domain
    superdomain_subdomains[superdomain].add(hostname)
    superdomain_count[superdomain]+=1

    #Parse the page and extract links
    soup = BeautifulSoup(response.text, "html.parser")

    #Find new links 
    for link in soup.find_all("a",href=True):
                    new_url = link["href"]
                    if not new_url.startswith("http"):
                        continue
                    new_hostname = urlparse(new_url).netloc
                    result=tldextract.extract(new_hostname)
                    new_superdomain=result.registered_domain
                    if new_superdomain in visited_domains:
                        continue
                    superdomain_subdomains[new_superdomain].add(new_hostname)
                    superdomain_count[new_superdomain]+=1
                    p = superdomain_count[new_superdomain]
                    s=len(superdomain_subdomains[new_superdomain])
                    combined_score=1/log2(p+2)+1/log2(s+2)
                    new_priority = -combined_score
                    pq.put((new_priority,new_url))
    
print("Crawling complete.")
print("Total unique domains visited:", len(visited_domains))