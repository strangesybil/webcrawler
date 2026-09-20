import requests
import time
import os
from threading import Lock
from datetime import datetime
from bs4 import BeautifulSoup
from queue import PriorityQueue
from collections import defaultdict
from urllib.parse import urljoin, urlparse
from math import log2
import tldextract 
from pybloom_live import BloomFilter 
from urllib.robotparser import RobotFileParser
from concurrent.futures import ThreadPoolExecutor
lock = Lock()

robots_cache = {}
NUM_WORKERS = 20

#Handle robots
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
visited_domains_bf=BloomFilter(capacity=20000, error_rate=0.01)#set of domains that have been visited - look at data structures that are thread safe, Bloomfilter, scalable, 10,000 
superdomain_count=defaultdict(int) #How many times have I seen this superdomain?
superdomain_subdomains=defaultdict(set) #set of subdomains for each superdomain
search_query=input("What are you looking for? ")
safe_query = search_query.replace(" ", "_") #Just in case there are spaces
run_folder = f"/Users/rae/Documents/crawled_pages/run_{safe_query}_{int(time.time())}" #Create crawl log, named by query and marked by UNIX timecode
os.makedirs(run_folder, exist_ok=True) #create the folder 
page_count=0 #How many pages crawled, incremented after successful fetch
log_file = open(f"{run_folder}/crawl_log.txt", "a", encoding="utf-8") #crawllog.txt 

seed_urls = ["https://bing.com/search",
            "https://en.wikipedia.org/w/index.php?search=" + search_query]


#Get initial search results from Bing and Wikipedia
for url in seed_urls:
    response = requests.get(
        url,
        params={"q": search_query},
        headers={"User-Agent": "SmallCrawler/1.0 (student project)"}
    )
    print("Seed page status:", response.status_code)


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
           priority=-combined_score #negate so it's popped first
           pq.put((priority,1,url))
           print(f"\nHow many items are in the queue? {pq.qsize()}")

def worker():
    global page_count
    while True:
        try: 
            priority,depth,url = pq.get(timeout=5)   
        except Exception: 
             return #queue empty for 5s, worker done
        
        print("DEQUEUED:", priority,depth,url) 
        hostname = urlparse(url).netloc
        result=tldextract.extract(hostname)
        superdomain=result.registered_domain

        with lock: 
            if url in visited_domains_bf:
                continue
            visited_domains_bf.add(url)

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
            with lock: 
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_file.write(f"URL: {url}, Size: {len(response.content)} bytes, Status: {response.status_code}, Depth: {depth}, Time: {timestamp}\n")
            print("Failed.")
            continue 
    
        #Successful visit and download
        hostname=urlparse(url).netloc
        result=tldextract.extract(hostname)
        superdomain=result.registered_domain

        #save fetched page
        with lock: 
            superdomain_subdomains[superdomain].add(hostname)
            superdomain_count[superdomain]+=1
            page_count+=1
            current_page_num=page_count

        safe_hostname = hostname.replace(".", "_").replace(":", "_")
        filename = f"{run_folder}/{current_page_num}_{safe_hostname}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(response.text)


        #write log
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        size = len(response.content)
        with lock:       
            log_file.write(f"URL: {url}, Size: {size} bytes, Status: {response.status_code}, Depth: {depth}, Time: {timestamp}\n")

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
                        with lock:
                            if new_url in visited_domains_bf:
                                print("SKIPPING (already visited):", new_url)
                                continue
                            superdomain_count[new_superdomain]+=1
                            p = superdomain_count[new_superdomain]
                            s=len(superdomain_subdomains[new_superdomain])

                        combined_score=1/log2(p+2)+1/log2(s+2)
                        new_priority = -combined_score
                        pq.put((new_priority,depth+1,new_url))
                        print(f"\nHow many items are in the queue? {pq.qsize()}")

with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
    for _ in range(NUM_WORKERS):
        executor.submit(worker)
   
print("Crawling complete.")
print("Total unique domains visited:", len(visited_domains_bf))
log_file.close()