from flask import Flask, jsonify, json
from flask_restful import Resource, Api, reqparse
from searchers import Searcher
import requests


app = Flask(__name__)
api = Api(app)


class RetrievalAPI(Resource):

    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('q', type=str)
        '''url = 'http://npmsearch.com/query?q='+parser.parse_args().get('q') +\
              '&size=200&fields=name,keywords,description,readme'''

        q = parser.parse_args().get('q')
        # n = '20'
        searcher = Searcher()
        print('Running metasearch')
        ranking, result = searcher.metasearch(q, 'javascript package')

        '''df = pd.read_json(json_string, encoding="utf-8")
        df = df.iloc[0:20, :]
        result = df["results"].to_json(orient='records')
        result = {"total": str(len(df)), "results": json.loads(result)}'''
        print(ranking)
        return jsonify(result)


api.add_resource(RetrievalAPI, '/retrieval', endpoint='retrieval')

if __name__ == '__main__':
    app.run(debug=True)