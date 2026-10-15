# search-api architecture

search-api serves /search. Queries go to elasticsearch. Historically a Redis result cache
(redis-search-cache) absorbed about 85% of read traffic for popular queries. Elasticsearch is
sized for cache-miss traffic only.
