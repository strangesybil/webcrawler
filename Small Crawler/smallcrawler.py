import requests
import os
from bs4 import BeautifulSoup
from queue import PriorityQueue
from collections import defaultdict
from urllib.parse import urljoin, urlparse
from math import log2
import tldextract 
from pybloom_live import BloomFilter 
from urllib.robotparser import RobotFileParser
from concurrent.futures import ThreadPoolExecutor

robots_cache = {}
NUM_WORKERS = 20

def get_robots_parser(hostname):
    if hostname in robots_cache: 
          return robots_cache[hostname]

    rp=RobotFileParser()
    robots_url = f"https://{hostname}/robots.txt"
    try: 
        rp.set_url(robots_url)
        rp.read()
    except Exception as e: 
          print(f"Could not fetch robots.txt for {hostname}:{e}")
          rp=None #no restrictions

    robots_cache[hostname] = rp
    return rp

headers = {
    "User-Agent": "SmallCrawler/1.0 (NYU student project)"
} 

#Initialize the queue
pq= PriorityQueue() #The queue of URLs to crawl
visited_domains_bf=BloomFilter(capacity=10000, error_rate=0.01)#set of domains that have been visited - look at data structures that are thread safe, Bloomfilter, scalable, 10,000 
superdomain_count=defaultdict(int) #How many times have I seen this superdomain?
superdomain_subdomains=defaultdict(set) #set of subdomains for each superdomain
os.makedirs("/Users/rae/Documents/crawled_pages", exist_ok=True) 
page_count=0 #How many pages crawled, incremented after successful fetch
search_query=input("What are you looking for? ")

seed_urls = ["https://bing.com/search",
            "https://en.wikipedia.org/w/index.php?search=" + search_query]


#Get initial search results from Bing and Wikipedia
for url in seed_urls:
    response = requests.get(
        url,
        params={"q": search_query},
        headers={"User-Agent": "RaeCrawler/1.0 (student project)"}
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
           page_count+=1
           safe_hostname=hostname.replace(".", "_").replace(":", "_")
           filename = f"/Users/rae/Documents/crawled_pages/{page_count}_{safe_hostname}.html"
           with open(filename, "w", encoding="utf-8") as f:
             f.write(response.text)
           p = superdomain_count[superdomain]
           s = len(superdomain_subdomains[superdomain])
           combined_score=1/log2(p+2)+1/log2(s+2)
           priority=-combined_score #negate so it's popped first?
           pq.put((priority,1,url))
           print(f"\nHow many items are in the queue? {pq.qsize()}")
    
while not pq.empty():
    priority,depth,url = pq.get()
    print("DEQUEUED:", priority,depth,url)   # add this
    hostname = urlparse(url).netloc
    result=tldextract.extract(hostname)
    superdomain=result.registered_domain
    if superdomain in visited_domains_bf:
        continue
    visited_domains_bf.add(superdomain)
    rp=get_robots_parser(hostname)
    if rp is not None and not rp.can_fetch("*", url):
        print("Blocked by robots.txt ",url)
        continue
    #Try to download pages in html
    try: 
        response=requests.get(url,timeout=5)
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
                    if new_superdomain in visited_domains_bf:
                        print("SKIPPING (already visited):", new_superdomain)
                        continue
                    superdomain_subdomains[new_superdomain].add(new_hostname)
                    superdomain_count[new_superdomain]+=1
                    p = superdomain_count[new_superdomain]
                    s=len(superdomain_subdomains[new_superdomain])
                    combined_score=1/log2(p+2)+1/log2(s+2)
                    new_priority = -combined_score
                    pq.put((new_priority,depth+1,new_url))
    
print("Crawling complete.")
print("Total unique domains visited:", len(visited_domains_bf))