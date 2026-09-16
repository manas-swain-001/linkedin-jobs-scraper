import jobs_scraper.storage as s

for p in s.load_posts():
    s.register_contacts(p["emails"], p["phones"])
    print("registered", p["emails"] or p["phones"])
print("contacts:", s.load_contacts())