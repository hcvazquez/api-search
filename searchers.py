from unicodedata import normalize
import pandas as pd
from flask import Flask, jsonify, json
import requests
from bs4 import BeautifulSoup
import numpy as np
import functools


class Searcher(object):

    def __init__(self, ranker_model='Models/GBRank_models', searcher_url='https://api.npms.io/v2/package/'):
        self.model = ranker_model
        self.url = searcher_url

    def retrieval(self, need, tech):

        dvectors = pd.DataFrame(columns=['NPMSearch', 'NPM', 'Bing'])

        def getPackageData(dvectors):

            def _removeNonAscii(s):
                return "".join(i for i in s if ord(i) < 128)

            ### BUILDING DATASET ###

            # extraer los nombres de todos los paquetes
            npmsearch = dvectors['NPMSearch'][dvectors['NPMSearch'].notnull()]
            npm = dvectors['NPM'][dvectors['NPM'].notnull()]

            list_names = pd.concat([npm, npmsearch], ignore_index=True).unique()

            pkgdata = pd.DataFrame(list_names, columns=['name'])

            def getNPMioInfo(pkg):
                header = {
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.75 Safari/537.36",
                    "X-Requested-With": "XMLHttpRequest"
                }
                response = requests.get("https://api.npms.io/v2/package/" + pkg, headers=header)
                r_npmsio = _removeNonAscii(response.text)
                return r_npmsio.lower()

            def npmio(row):
                return getNPMioInfo(row['name'])

            def getLinks(rowi):
                pkg = rowi['name']
                row = pkgdata.index[pkgdata['name'] == pkg]
                if len(row) > 0:
                    js = json.loads(pkgdata.iloc[row[0]]['npmio'])
                    if 'collected' in js:
                        try:
                            dic = json.loads(pkgdata.iloc[row[0]]['npmio'])["collected"]["metadata"]["links"]
                            return dic
                        except:
                            dic = {}
                    return {}
                else:
                    return {}

            def getLink(row, link):
                links = row['links']
                for key, value in links.items():
                    if key == link:
                        return value
                return ""

            pkgdata['npmio'] = pkgdata.apply(lambda row: npmio(row), axis=1)
            pkgdata['links'] = pkgdata.apply(lambda row: getLinks(row), axis=1)
            pkgdata['npm'] = pkgdata.apply(lambda row: getLink(row, 'npm'), axis=1)
            pkgdata['homepage'] = pkgdata.apply(lambda row: getLink(row, 'homepage'), axis=1)
            pkgdata['repository'] = pkgdata.apply(lambda row: getLink(row, 'repository'), axis=1)

            return pkgdata

        def getNPMSearchRanking(need):
            def _removeNonAscii(s):
                return "".join(i for i in s if ord(i) < 128)

            url = 'http://npmsearch.com/query?q=' + need + \
                  '&size=200&fields=name,keywords,description,readme,homepage'
            header = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.75 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest"
            }
            r = requests.get(url, headers=header)

            json_string = r.text

            json_string = _removeNonAscii(json_string)

            ### BUILDING DATASET ###

            npmsearch = pd.read_json(json_string.lower(), encoding="utf-8")
            npmsearch = npmsearch.iloc[:, :]

            # extraer los nombres de todos los paquetes
            def naming(row):
                return row["results"]["name"][0]

            npmsearch['name'] = npmsearch.apply(lambda row: naming(row), axis=1)
            return npmsearch["name"]

        def getNPMRanking(need):
            header = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.75 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest"
            }
            response = requests.get("https://www.npmjs.com/search?q=" + need, headers=header)
            soup = BeautifulSoup(response.text, 'html.parser')
            npm = []
            for h3 in soup.select("div[class^=search__packageList]")[0].select("h3[class^=package-list-item]"):
                npm.append(h3.text)
            return pd.Series(npm)

        def getBingRanking(need, tech, pkgdata):
            q = tech + need
            l = '20'

            gheader = {
                "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36"
            }
            response = requests.get("https://www.bing.com/search?q=" + q + "&num=" + l, headers=gheader)

            soup = BeautifulSoup(response.text, 'html.parser')

            elements = soup.select("h2 a");
            r_urls = []
            for i in range(1, len(elements)):
                elem = elements[i]
                r_urls.append(elem.get('href'))

            def getSoup(url):
                gheader = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36"
                }
                response = requests.get(url, headers=gheader)
                return BeautifulSoup(response.text, 'html.parser')

            text = ""
            for uri in r_urls:
                text += " " + getSoup(r_urls[0]).get_text()

            return pd.Series(self.entityExtraction(text, pkgdata))

        dvectors['NPMSearch'] = getNPMSearchRanking(need)
        dvectors['NPM'] = getNPMRanking(need)

        pkgdata = getPackageData(dvectors)
        dvectors['Bing'] = getBingRanking(need, tech, pkgdata)

        return dvectors, pkgdata

    def entityExtraction(self, text, npmsearch):
        matches = []
        wordList = text.lower().split()

        for word in wordList:
            if len(npmsearch.index[npmsearch['name'] == word].tolist()) > 0 and word not in matches:
                matches.append(word)
            elif len(npmsearch.loc[npmsearch["name"].str.startswith(word), "name"].tolist()) > 0:
                pkg = npmsearch.loc[npmsearch["name"].str.startswith(word), "name"].values[0]
                if pkg not in matches:
                    matches.append(pkg)
            elif len(npmsearch["name"].values) > 0:
                for pkg in npmsearch["name"].values:
                    if word.startswith(pkg) and pkg not in matches:
                        matches.append(pkg)
            elif len(npmsearch.index[npmsearch['npm'] == word].tolist()) > 0:
                ix = npmsearch.index[npmsearch['npm'] == word].tolist()[0]
                pkg = npmsearch.iloc[ix]['name']
                if pkg not in matches:
                    matches.append(pkg)
            elif len(npmsearch.index[npmsearch['homepage'] == word].tolist()) > 0:
                ix = npmsearch.index[npmsearch['homepage'] == word].tolist()[0]
                pkg = npmsearch.iloc[ix]['name']
                if pkg not in matches:
                    matches.append(pkg)
            elif len(npmsearch.index[npmsearch['repository'] == word].tolist()) > 0:
                ix = npmsearch.index[npmsearch['repository'] == word].tolist()[0]
                pkg = npmsearch.iloc[ix]['name']
                if pkg not in matches:
                    matches.append(pkg)

        return matches

    def aggregate(self, rankings):

        rankings = [rankings['NPMSearch'], rankings['NPM'], rankings['Bing']]

        def getUniqueItems(rankings):
            uniqueItems = []
            for r in rankings:
                for ri in r:
                    if ri not in uniqueItems and isinstance(ri, str):
                        uniqueItems.append(ri)
            return uniqueItems

        def getPointsUnassigned(i):
            result = 0;
            for e in range(1, i + 1):
                result += e
            return result

        def bordaScoring(rankings, uniqueItems):
            result = {}
            for ranking in rankings:
                scoreRest = getPointsUnassigned(len(uniqueItems) - len(ranking))
                for ri in uniqueItems:
                    score = 0.0
                    if scoreRest > 0 and ri in ranking.values:
                        score = len(uniqueItems) - (ranking[ranking == ri].index[0] + 1)
                    elif (len(uniqueItems) - len(ranking)) > 0:
                        score = scoreRest / (len(uniqueItems) - len(ranking))

                    if ri in result:
                        result[ri] = result[ri] + score
                    else:
                        result[ri] = score

            return result

        def compare(item1, item2):
            if scoring[item1] == scoring[item2]:
                return 0
            elif scoring[item1] > scoring[item2]:
                return 1
            return -1

        uniqueItems = getUniqueItems(rankings)
        scoring = bordaScoring(rankings, uniqueItems)

        rank_aggregated = sorted(uniqueItems, key=functools.cmp_to_key(compare), reverse=True)
        return rank_aggregated

    def getJSONResults(self, ranking, pkgdata):

        def getPkg(pkg, pkgdata):
            row = pkgdata.index[pkgdata['name'] == pkg]
            if len(row) > 0:
                js = json.loads(pkgdata.iloc[row[0]]['npmio'])
                if 'collected' in js:
                    try:
                        package = json.loads(pkgdata.iloc[row[0]]['npmio'])["collected"]["metadata"]
                        package = {k: package[k] for k in
                                   package.keys() & {'name', 'scope', 'version', 'description', 'keywords', 'date',
                                                     'links', 'publisher', 'maintainers'}}
                        score = json.loads(pkgdata.iloc[row[0]]['npmio'])["score"]
                        return package, score
                    except:
                        return {}, {}
            return {}, {}

        results = []
        for pkg in ranking:
            result = {}
            package, score = getPkg(pkg, pkgdata)
            if not package:
                print("package not found: " + pkg)
            else:
                result['package'] = package
                result['score'] = score
                result['searchScore'] = len(ranking) - ranking.index(pkg)
                results.append(result)

        json_results = {}
        json_results['total'] = len(ranking)
        json_results['results'] = results

        return json_results

    def metasearch(self, need, tech):

        rankings, pkgdata = self.retrieval(need, tech)
        ranking = self.aggregate(rankings)
        return ranking, self.getJSONResults(ranking, pkgdata)