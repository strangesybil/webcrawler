from math import log10
import requests
import threading
import time
from bs4 import BeautifulSoup
from queue import PriorityQueue
from collections import defaultdict
#Use defaultdict because it will automatically create a new entry with a default value of 0 for any new domain encountered, eliminating the need to check if the domain already exists in the dictionary before incrementing its count.
from urllib.parse import urlparse

domain_counts = defaultdict(int) #How many times have I seen this domain?

# Initialize a priority queue for URLs not crawled
pq=PriorityQueue()

#Check if we've visited a URL before
visited_urls=set()

#What is the user looking for? 
search_query = input("What are you looking for?")

#Where am I getting the results from? 
seed_url = ["https://bing.com/search"]

#Get initial search results
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
        url = link["href"]
        if url.startswith("http"):
            print(url) #print legitimate links
            #Figure out scoring priority for links
            domain=urlparse(url).netloc #Find url domain name
            hostname=urlparse(url).hostname #Find url hostname
            #Find how many times I've seen the hostname
            priority=domain_counts[domain] #How many times have I seen this domain?
            pq.put((priority,url)) #Add links and priority (based on newness) to priority queue - because Python returns smallest number first. 
            print(f"\nHow many items are in the queue? {pq.qsize()}")
   #Start crawling the links in the priority queue     
    while not pq.empty():
        #Acquire and remove first item from the priority queue / Smallest number = highest priority  
        priority, item=pq.get() #tuple of priority and url
        if item in visited_urls:
            continue #Skip if already visited

        visited_urls.add(item) #You have now visited this URL
        #Try to download pages in html
        try: 
            response=requests.get(item)
            with open(f"/Users/rae/Documents/source1.html", "w",encoding="utf-8") as f:
                f.write(response.text)
        except requests.exceptions.RequestException as e:
            print("Request failed:", e)
            continue
        #Only count successful responses (status code 200) for scoring
        if response.status_code != 200:
            print("Failed.")
            continue 

        #Successful visitation
        domain = urlparse(item).netloc
        domain_counts[domain] += 1
        print("Domain",domain)
        print("/nPages crawled from this domain:", domain_counts[domain])
        
        #Parse the response text using BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")

        #Find new links
        for link in soup.find_all("a",href=True):
                new_url = link["href"]
                if not new_url.startswith("http"):
                    continue
                if new_url in visited_urls:
                    continue
                new_domain = urlparse(new_url).netloc

                new_priority = domain_counts[new_domain]
                pq.put((new_priority,new_url))

print("Crawling complete.")
print("Total unique domains visited:", len(visited_urls))
            





      


