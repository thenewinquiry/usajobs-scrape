"""
example job listing:

    {
        'PositionID': 'JV-17-JEH-1938937',
        'ClockDisplay': '',
        'ShowMapIcon': True,
        'SalaryDisplay': 'Starting at $71,466 (VN 00)',
        'Title': 'Nurse Manager - Cardiology Service',
        'HiringPath': [{
            'IconClass': 'public',
            'Font': 'fa fa-users',
            'Tooltip': 'Jobs open to U.S. citizens, national or individuals who owe allegiance to the U.S.'
        }],
        'Agency': 'Veterans Affairs, Veterans Health Administration',
        'LocationLatitude': 33.7740173,
        'LocationLongitude': -84.29659,
        'WorkSchedule': 'Full Time',
        'Location': 'Decatur, Georgia',
        'Department': 'Department of Veterans Affairs',
        'WorkType': 'Agency Employees Only',
        'DocumentID': '467314300',
        'DateDisplay': 'Open 04/20/2017 to 05/16/2017'
    }
"""

import json
import requests
from time import sleep
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = 'https://www.usajobs.gov'
INTERVAL = 60 * 60 * 12


def scrape(query, page=1):
    print('scraping page: {}'.format(page))
    url = '{base}/Search/?k={query}&p={page}'.format(
        base=BASE_URL, query=query, page=page)
    resp = requests.get(url)
    html = resp.text
    soup = BeautifulSoup(html, 'html.parser')
    search_id = soup.find(attrs={'id' : 'UniqueSearchID'}).attrs['value']

    cookies = dict(resp.cookies)
    headers = {
        'Origin': BASE_URL,
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.96 Safari/537.36',
        'Content-Type': 'application/json; charset=UTF-8',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Referer': url,
        'X-Requested-With': 'XMLHttpRequest',
        'Connection': 'keep-alive',
    }
    data = {
        'GradeBucket': [],
        'JobCategoryCode': [],
        'LocationName': [],
        'PostingChannel': [],
        'Department': [],
        'Agency': [],
        'PositionOfferingTypeCode': [],
        'TravelPercentage': [],
        'PositionScheduleTypeCode': [],
        'SecurityClearanceRequired': [],
        'ShowAllFilters': [],
        'HiringPath': [],
        'Keyword': query,
        'Page': page,
        'UniqueSearchID': search_id
    }

    resp = requests.post('{base}/Search/ExecuteSearch'.format(base=BASE_URL),
                         headers=headers, cookies=cookies, data=json.dumps(data))
    payload = json.loads(resp.text)
    results = payload['Jobs']

    for r in results:
        r['html'] = fetch_html(r)
        if r['Location'] == 'Multiple Locations':
            r['Locations'] = scrape_locations(r['html'])

    if (payload['Pager']['CurrentPageIndex'] <= payload['Pager']['LastPageIndex']):
        next = payload['Pager']['NextPageIndex']
        fetched = False
        while not fetched:
            try:
                results.extend(scrape(query, page=next))
                fetched = True
            except requests.exceptions.ConnectionError:
                sleep(5)
    return results


def fetch_html(job):
    id = job['DocumentID']
    url = '{}/GetJob/ViewDetails/{}'.format(BASE_URL, id)
    resp = requests.get(url)
    return resp.text


def scrape_locations(html):
    soup = BeautifulSoup(html, 'html.parser')
    els = soup.select('#additional-locations li a')
    if not els:
        els = soup.select('.usajobs-joa-intro__summary li a')
    locs = []
    for el in els:
        locs.append({
            'name': el.attrs['data-name'],
            'lat': el.attrs['data-coord-lat'],
            'lng': el.attrs['data-coord-long']
        })
    return locs


def on_job(job):
    """called on a new job listing, e.g. post to twitter or sth"""
    with open('/tmp/ice_jobs.txt', 'a') as f:
        f.write('{} ({})'.format(job['Title'], job['Location']))


if __name__ == '__main__':
    try:
        seen = json.load(open('data/.seen.json', 'r'))
    except FileNotFoundError:
        seen = []

    while True:
        results = scrape('immigration')
        jobs = {}
        for job in results:
            id = job['PositionID'] # alternatively, 'DocumentID'
            if id not in seen:
                jobs[id] = job
                on_job(job)
                seen.append(id)

        if jobs:
            with open('data/{}.json'.format(datetime.now().isoformat()), 'w') as f:
                json.dump(jobs, f)

        with open('data/.seen.json', 'w') as f:
            json.dump(seen, f)
        print('done')

        sleep(INTERVAL)
