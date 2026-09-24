+--------------------------------------------------------------+
|                      SMALL CRAWLER 1.0                       |
+--------------------------------------------------------------+

MAIN FILE: smallcrawler.py (Python)

DESCRIPTION:
------------
When run, the crawler asks the user what they are looking for.
After the user enters a search query, the crawler asks which
seed bank they would like to use and you will be given a choice between
seed bank 1 and seed bank 2.

  [SEED BANK 1] General inquiries
      e.g. Sandra Bullock, Ryan Gosling, Italy, etc.

  [SEED BANK 2] Medical-related inquiries
      e.g. eczema, desmoid tumor, etc.

SUBMITTED FILES:
-----------------
  * smallcrawler.py
  *crawl_log_desmoid_tumor.txt   (Seed bank 2 run)
  *crawl_log_sandra_bullock.txt  (Seed bank 1 run)
  *explain.txt - description of project

RESULTS:
--------
  Both searches successfully crawled over 5,000 webpages
  within 10 minutes.

  Each log line contains (unless blocked by robots.txt or failed):
    NO. OF PAGE CRAWLED | URL | Timestamp | Size (bytes) | Depth | Status Code

+--------------------------------------------------------------+