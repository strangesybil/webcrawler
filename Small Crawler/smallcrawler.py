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
NUM_WORKERS = 40

#Handle robots - be polite!
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
    "User-Agent": "SmallCrawler/1.0 (student project)"
} 

#Initialize the queue
pq= PriorityQueue() #The queue of URLs to crawl
visited_domains_bf=BloomFilter(capacity=20000, error_rate=0.01) 
superdomain_count=defaultdict(int) #How many times have I seen this superdomain?
superdomain_subdomains=defaultdict(set) #set of subdomains for each superdomain
search_query=input("What are you looking for? ")
safe_query = search_query.replace(" ", "_") #Just in case there are spaces
run_folder = f"/Users/rae/Documents/crawled_pages/run_{safe_query}_{int(time.time())}" #Create crawl log, named by query and marked by UNIX timecode
os.makedirs(run_folder, exist_ok=True) #create the folder 
page_count=0 #How many pages crawled, incremented after successful fetch
log_file = open(f"{run_folder}/crawl_log.txt", "a", encoding="utf-8") #crawllog.txt 

seed_set_1 = [ # general ie. sandra bullock
    "https://bing.com/search",
    "https://en.wikipedia.org/w/index.php?search=" + search_query,
    "https://www.bbc.com/search?q="+ search_query
]

seed_set_2 = [ #Medical stuff ie. tumor
    "https://www.mayoclinic.org/diseases-conditions/search-results?q="+ search_query,
    "https://www.google.com/search?q=" + search_query
]
run_choice = input("Which seed set? (1 or 2): ")
seed_urls = seed_set_1 if run_choice == "1" else seed_set_2

for url in seed_urls:
    response = requests.get(
        url,
        params={"q":search_query},
        headers={"User-Agent": "SmallCrawler/1.0 (student project)"}
    )
    print("Seed page status:", response.status_code)

    #Use BeautifulSoup library to parse initial search results and extract links
    soup = BeautifulSoup(response.text, "html.parser")

    for link in soup.find_all("a",href=True):
       url=link["href"]
       if url.startswith("http"): # Let's say "https://speedrun.a16z.com/alpha?ref=a002-marketo-blast-to-tech-week&__s=juvolj8emvd379oemwbu"
           hostname=urlparse(url).netloc # "speedrun.a16z.com"
           result=tldextract.extract(hostname) # "a16z.com" 
           superdomain=result.registered_domain # saves a16z.com
           superdomain_count[superdomain]+=1 #Not incrementing superdomain_subdomains because I haven't crawled it yet
           p = superdomain_count[superdomain]
           s = len(superdomain_subdomains[superdomain])
           combined_score=1/log2(p+2)+1/log2(s+2) #First pass:1/(log2(1+3))+1/(log2(2)) = 1.63 before negation / Second pass: 
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

        try:
            print("DEQUEUED:", priority,depth,url) 
            hostname = urlparse(url).netloc
            result=tldextract.extract(hostname)
            superdomain=result.registered_domain

            with lock: 
                if url in visited_domains_bf: #Have I visited before? 
                    continue
                visited_domains_bf.add(url)

            rp=get_robots_parser(hostname)
            if rp is not None and not rp.can_fetch("*", url): #Add to log that was blocked by robots.txt
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with lock: 
                    log_file.write(f"No: {pq.qsize()}, URL: {url}, Depth: {depth}, Time: {timestamp}\n")
                print("Blocked by robots.txt ",url)
                continue

            #Try to download pages in html - get response first 
            try: 
                response=requests.get(url,timeout=5)
            except requests.exceptions.RequestException as e:
                print("Request failed:", e)
                continue
                #Only count successful responses (status code 200) for scoring
            if response.status_code != 200:
                with lock: #Write failed attempts
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    log_file.write(f"URL: {url}, Size: {len(response.content)} bytes, Status: {response.status_code}, Depth: {depth}, Time: {timestamp}\n")
                print("Failed.")
                continue 
        
            hostname=urlparse(url).netloc
            result=tldextract.extract(hostname)
            superdomain=result.registered_domain

            
            with lock: 
                superdomain_subdomains[superdomain].add(hostname) #Increment subdomains visited after successful visit
                superdomain_count[superdomain]+=1
                page_count+=1
                current_page_num=page_count

            #save file
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
        except Exception as e: 
             print(f"Worker error on {url}: e")
             continue

with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = [executor.submit(worker) for _ in range(NUM_WORKERS)]
        for f in futures:
            f.result() #in case worker died from uncaught exception
   
print("Crawling complete.")
print("Total unique domains visited:", len(visited_domains_bf))
log_file.close()