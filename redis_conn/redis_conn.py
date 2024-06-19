import aioredis

async def get_redis_connection():
    host = "147.45.237.234"   
    port = 6379              
    password = "dE*if@y7w/BtA%"  
    db_index = 1              

    redis = await aioredis.create_redis_pool(
        f"redis://{host}:{port}", 
        encoding="utf-8", 
        db=db_index, 
        password=password
    )
    return redis
