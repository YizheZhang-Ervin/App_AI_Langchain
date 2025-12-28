# Weaviate 使用
# install
# pip install -U weaviate-client

import weaviate

# connect  =========================================================
client = weaviate.connect_to_local(
    host="localhost",
    port=8080,
    grpc_port=50051,
)

print(client.is_ready())

# create collection =========================================================
client.collections.create("Database")

# create object =========================================================
database = client.collections.get("Database")
uuid = database.data.insert(
    properties={
        "segment_id": "1000",
        "document_id": "1",
    },
    # 复制生成1536维向量
    vector=[0.12345] * 1536
)

print(uuid)

# insert object =========================================================
uuid = database.data.insert(
    properties={
        "segment_id": "1000",
        "document_id": "1",
    },
    # 复制生成1536维向量
    vector=[0.12345] * 1536,
    uuid=uuid.uuid4()
)

# batch import =========================================================
# 生成5条数据
data_rows = [{"title": f"标题{i + 1}"} for i in range(5)]
# 生成5个对应的向量数据
vectors = [[0.1] * 1536 for i in range(5)]
# 集合对象
collection = client.collections.get("Database")
# 批处理大小为200
with collection.batch.fixed_size(batch_size=200) as batch:
    for i, data_row in enumerate(data_rows):
        # 批量导入对象
        batch.add_object(
            properties=data_row,
            vector=vectors[i],
            # 指定uuid
            uuid=uuid.uuid4()
        )
        # 超过10个则终止导入
        if batch.number_errors > 10:
            print("批量导入对象出现错误次数过多，终止执行")
            break
# 打印处理失败对象
failed_objects = collection.batch.failed_objects
if failed_objects:
    print(f"导入失败数量: {len(failed_objects)}")
    print(f"第一个导入失败对象: {failed_objects[0]}")

# search =========================================================
database = client.collections.get("Database")

# 通过uuid获取对象信息，并且返回向量信息
data_object = database.query.fetch_object_by_id(
    "a60f4b19-9c97-4eb0-ba02-8c7b0a6cfcb1",
    include_vector=True
)

# 打印向量信息
print(data_object.properties)
print(data_object.vector["default"])

# search all =========================================================
collection = client.collections.get("Database")

for item in collection.iterator(
    include_vector=True
):
    print(item.properties)
    print(item.vector)

# update  =========================================================
database = client.collections.get("Database")
database.data.update(
    uuid="a60f4b19-9c97-4eb0-ba02-8c7b0a6cfcb1",
    # 更新属性
    properties={
        "segment_id": "2000",
    },
    # 更新向量信息
    vector=[1.0] * 1536
)

# replace  =========================================================
database = client.collections.get("Database")
database.data.replace(
    uuid="a60f4b19-9c97-4eb0-ba02-8c7b0a6cfcb1",
    properties={
        "segment_id": "3000",
    },
    vector=[1.0] * 1536
)

# delete 1  =========================================================
database = client.collections.get("Database")
database.data.delete_by_id(
    "a60f4b19-9c97-4eb0-ba02-8c7b0a6cfcb1"
)

# delete 2  =========================================================
database = client.collections.get("Database")
database.data.delete_many(
    where=Filter.by_property("title").like("标题*")
)

# delete 3  =========================================================
client.collections.delete(
    "Database"
)