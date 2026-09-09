import requests
from bs4 import BeautifulSoup
from queue import PriorityQueue

# Initialize a priority queue for the search results
pq=PriorityQueue()

search_query = input("What are you looking for?")

seed_url = ["https://google.com/search",
            "https://bing.com/search",
            "https://duckduckgo.com/search"]

for url in seed_url:
    response = requests.get(
        url,
        params={"q": search_query},
    )

    print(response.status_code)

    with open(f"/Users/rae/Documents/source.html", "w",encoding="utf-8") as f:
        f.write(response.text)

    soup = BeautifulSoup(response.text, "html.parser")

    for link in soup.find_all("a",href=True):
        print(link["href"])
        url = link["href"]
        pq.put(url)



      


