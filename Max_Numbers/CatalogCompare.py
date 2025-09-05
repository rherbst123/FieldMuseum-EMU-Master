# Open and read URLs from a file
with open('/home/riley/Documents/Work/300Images', 'r') as file:
    for url in file:
        url = url.strip()
        if url: 
            url = url.rsplit('/', 1)[1]
            url = url.rsplit('.jpg',1)[0]
            print(url)
