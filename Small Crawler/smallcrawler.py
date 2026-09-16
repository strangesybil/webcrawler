import requests
from bs4 import BeautifulSoup
from queue import PriorityQueue
from collections import defaultdict
from urllib.parse import urljoin, urlparse
import tldextract

#Initialize the queue
pq= PriorityQueue(maxsize=100) #The queue of URLs to crawl
hostname_count=defaultdict(int) #How many times have I seen this domain?
visited_domains=set()#set of domains that have been visited
superdomain_count=defaultdict(int) #How many times have I seen this superdomain?
superdomain_visited=set() #set of superdomains that have been visited
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
           priority=superdomain_count[superdomain]
           pq.put((priority,url))
           print(f"\nHow many items are in the queue? {pq.qsize()}")
    
while not pq.empty():
    priority,url = pq.get()
    if url in visited_domains:
        continue

    visited_domains.add(url)
    #Try to download pages in html
    try: 
        response=requests.get(url)
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
    hostname_count[hostname]+=1
    print("Domain",hostname)
    print("/nPages crawled from this domain:", hostname_count[hostname])

    #Parse the page and extract links
    soup = BeautifulSoup(response.text, "html.parser")

    #Find new links 
    for link in soup.find_all("a",href=True):
                    new_url = link["href"]
                    if not new_url.startswith("http"):
                        continue
                    if new_url in visited_domains:
                        continue
                    new_domain = urlparse(new_url).netloc
    
                    new_priority = hostname_count[new_domain]
                    pq.put((new_priority,new_url))
    
    print("Crawling complete.")
    print("Total unique domains visited:", len(visited_domains))