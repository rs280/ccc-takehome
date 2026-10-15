# orders-api architecture

orders-api serves order history and order details. Every GET /orders/{id} calls inventory-service
synchronously for stock status with a 5000ms timeout and no fallback.
