# checkout-api architecture

checkout-api handles cart and checkout. POST /api/checkout opens a database transaction against
postgres-checkout using a connection pool sized by the pool size setting, reserves stock through
inventory-service and charges through payments-api. frontend-web calls checkout-api.
