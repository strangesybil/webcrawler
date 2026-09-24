import requests
import time
import os
from threading import Lock
from datetime import datetime
from bs4 import BeautifulSoup
from queue import PriorityQueue
from collections import defaultdict
from urllib.parse import urljoin, urlparse, urlunparse
from math import log2
import tldextract 
from pybloom_live import BloomFilter 
from urllib.robotparser import RobotFileParser
from concurrent.futures import ThreadPoolExecutor
lock = Lock()

robots_cache = {}
mylittleworkers = 40

pq= PriorityQueue() #The queue of URLs to crawl - remember that pq.get will return smallest numbers first
visited_urls_bf=BloomFilter(capacity=1000000, error_rate=0.01) 
superdomain_count=defaultdict(int) #How many times have I seen this superdomain?
superdomain_subdomains=defaultdict(set) #set of subdomains for each superdomain
search_query=input("What are you looking for? ")
safe_query = search_query.replace(" ", "_") #Just in case there are spaces
run_folder = f"/Users/rae/Documents/crawled_pages/run_{safe_query}_{int(time.time())}" #Create crawl log, named by query and marked by UNIX timecode
os.makedirs(run_folder, exist_ok=True) #create the folder 
log_file = open(f"{run_folder}/crawl_log.txt", "a", encoding="utf-8") #crawllog.txt 
num_errors=0 #num of 404 errors
start_time = time.time() 
success_count=0

blacklist = {
".pdf", ".jpg", ".jpeg", ".png", ".gif", ".mp3", ".mov", ".tar", ".mp4", ".json", ".doc", ".docx", ".aac", ".arc", ".avif", ".avi", ".azw", ".bz", ".bz2", ".bin", ".dmg", ".epub", ".gz", ".csv", ".css", ".jar", ".ppt", ".pptx", ".rar", ".sh", ".svg", ".xml", ".xls", ".xlsx", ".3gp", ".7z"
}

def filefilter(url): # no weird files 
    path=urlparse(url).path.lower() #finds the path of the url and converts to lowercase so that we can check if it's a weird file
    return any(path.endswith(x) for x in blacklist) #do any of the endings match the strings in blacklist? 

#Handle robots - be polite!
def bad_robots(hostname):
    if hostname in robots_cache: 
          return robots_cache[hostname]

    rp=RobotFileParser()
    robots_url = f"https://{hostname}/robots.txt"
    try:
        resp=requests.get(robots_url,headers=headers,timeout=5) #Robots can be slow :/, make sure they're not
        rp.parse(resp.text.splitlines()) #Splits string into individual lines so palatable for rp.parse
    except Exception as e: 
          print(f"Could not fetch robots.txt for {hostname}:{e}")
          rp=None #no restrictions

    robots_cache[hostname] = rp
    return rp

headers = {
    "User-Agent": "SmallCrawler/1.0 (student project)"
} 

def normalize_url(url):
     parsed = urlparse(url)
     path = parsed.path.rstrip("/") or "/"
     normalized_url = urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path,
    "", 
    "", 
    "")) #access path, .COM and lowers everything and removes query parameters fragments
     return normalized_url


seed_set_1 = [ # general ie. sandra bullock
    "https://www.bing.com/search?q="+search_query,
    "https://en.wikipedia.org/w/index.php?search="+search_query,
    "https://www.bbc.com/search?q="+search_query,
    "https://www.hellomagazine.com/us/"
    
]

seed_set_2 = [ #Medical stuff ie. tumor
    "https://www.mayoclinic.org/diseases-conditions/search-results?q="+search_query,
    "https://www.webmd.com/search?query="+search_query,
    "https://www.citymedphysio.co.nz"
]

run_choice = input("Which seed set? (1[general]or 2[medical]): ")
seed_urls = seed_set_1 if run_choice == "1" else seed_set_2

for seeds in seed_urls:
    seed_hostname=urlparse(seeds).netloc
    rp=bad_robots(seed_hostname)
    if rp is not None and not rp.can_fetch("*", seeds): 
        print("Blocked by robots.txt ",seeds)
        continue
    response = requests.get(
        seeds,
        headers=headers,
        timeout=5
    )
    print("Seed page status:", response.status_code)

    #Use BeautifulSoup library to parse initial search results and extract links
    soup = BeautifulSoup(response.text, "html.parser")

    for alphabet in soup.find_all("a",href=True):
       url=alphabet["href"]
       if url.startswith("http") and not filefilter(url): # Let's say "https://speedrun.a16z.com/alpha?ref=a002-marketo-blast-to-tech-week&__s=juvolj8emvd379oemwbu"
           hostname=urlparse(url).netloc # "speedrun.a16z.com"
           result=tldextract.extract(hostname) # "a16z.com" 
           superdomain=result.top_domain_under_public_suffix # saves a16z.com
           p = superdomain_count[superdomain]
           s = len(superdomain_subdomains[superdomain])
           combined_score=1/log2(p+2)+1/log2(s+2) #First pass:1/(log2(1+3))+1/(log2(2)) = 1.63 before negation / Second pass: 
           priority=-combined_score #negate so it's popped first
           pq.put((priority,1,url))
           print(f"\nHow many items are in the queue? {pq.qsize()}")

def workerbee():
    global success_count, num_errors
    while True:
        try: 
            priority,depth,url = pq.get(timeout=5)   
        except Exception: 
             return #queue empty for 5s, worker done

        try:
            print("DEQUEUED:", priority,depth,url) 
            hostname = urlparse(url).netloc
            result=tldextract.extract(hostname)
            superdomain=result.top_domain_under_public_suffix        

            normalized_url=normalize_url(url)
            with lock: 
                if normalized_url in visited_urls_bf: #Have I visited before? Don't visit those where the robots rejected me before. 
                    continue
                visited_urls_bf.add(normalized_url) #normalized url 
                
            rp=bad_robots(hostname)
            if rp is not None and not rp.can_fetch("*", url): 
                print("Blocked by robots.txt ",url)
                continue

            #Try to download pages in html - get response first 
            try: 
                response=requests.get(url, headers=headers, timeout=5)
            except requests.exceptions.RequestException as e:
                print("Request failed:", e)
                continue
                #Only count successful responses (status code 200) for scoring
            if response.status_code != 200:
                with lock: #Write failed attempts
                    num_errors=num_errors+1
                continue 

            content_type=response.headers.get("Content-Type","") #Checks if I'm looking through HTML or something else 
            if "text/html" not in content_type:
                 print("Not HTML. Skip ",url,content_type)
                 continue 

        
            hostname=urlparse(url).netloc
            result=tldextract.extract(hostname)
            superdomain=result.top_domain_under_public_suffix

            with lock:
                visited_urls_bf.add(normalize_url(response.url)) #In case final destination was different
                superdomain_subdomains[superdomain].add(hostname) #Increment subdomains visited after successful visit
                
            #write log
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            size = len(response.content)
            with lock:  
                success_count+=1
                successfulcrawl=success_count  
                elapsed = time.time() - start_time
                minutes, seconds = divmod(elapsed, 60)
                hours, minutes = divmod(minutes, 60)
                log_file.write(f"Num of 404/errors: {num_errors},Crawled: {successfulcrawl},URL: {url}, Size: {size} bytes, Status: {response.status_code}, Depth: {depth}, Time: {timestamp}, Elapsed time: {int(hours)}h {int(minutes)}m {seconds:.1f}s\n")
                

            #Parse the page and extract links
            soup = BeautifulSoup(response.text, "html.parser")

            #Find new links 
            for link in soup.find_all("a",href=True):
                            new_url = link["href"]
                            if not new_url.startswith("http") or filefilter(new_url):
                                continue
                            new_hostname = urlparse(new_url).netloc
                            result=tldextract.extract(new_hostname)
                            new_superdomain=result.top_domain_under_public_suffix
                            normalized_new_url=normalize_url(new_url)
                            with lock:
                                if normalized_new_url in visited_urls_bf:
                                    print("SKIPPING (already visited):", normalized_new_url)
                                    continue
                                superdomain_count[new_superdomain]+=1
                                p = superdomain_count[new_superdomain]
                                s=len(superdomain_subdomains[new_superdomain])

                            combined_score=1/log2(p+2)+1/log2(s+2)
                            new_priority = -combined_score
                            pq.put((new_priority,depth+1,new_url))
                            print(f"\nHow many items are in the queue? {pq.qsize()}")
        except Exception as e: 
             print(f"Worker error on {url}: {e}")
             continue

with ThreadPoolExecutor(max_workers=mylittleworkers) as executor:
        futures = [executor.submit(workerbee) for _ in range(mylittleworkers)]
        for f in futures:
            f.result() #in case worker died from uncaught exception
   
print("Crawling complete.")
print("Total unique urls crawled: ", success_count) 
print("Total unique urls visited (not crawled): ", len(visited_urls_bf)) 
print(f"No. of 404/errors:{num_errors}")
log_file.close()