import requests
import threading
import time
from bs4 import BeautifulSoup
from queue import PriorityQueue

# Initialize a priority queue for the search results
pq=PriorityQueue()

#What is the user looking for? 
search_query = input("What are you looking for?")

#Where am I getting the results from? 
seed_url = ["https://bing.com/search"]

#Get search results from all the seed pages 
for url in seed_url:
    response = requests.get(
        url,
        params={"q": search_query},
    )

    print(response.status_code)

#Download pages in html 
    with open(f"/Users/rae/Documents/source.html", "w",encoding="utf-8") as f:
        f.write(response.text)

#Use BeautifulSoup library to parse response text 
    soup = BeautifulSoup(response.text, "html.parser")

    for link in soup.find_all("a",href=True):
        print(link["href"])
        url = link["href"]
        if url.startswith("http"):
            #Figure out scoring priority for links
            pq.put(url) #Add links to priority queue
            print(f"\nHow many items are in the queue? {pq.qsize()}")
        
    while not pq.empty():
        #Acquire and remove first item from the priority queue    
        item=pq.get()
        #Download pages in html
        response=requests.get(item)
        with open(f"/Users/rae/Documents/source1.html", "w",encoding="utf-8") as f:
            f.write(response.text)
        #Parse the response text using BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")


      


