import json
import hashlib
from pydantic import BaseModel



def hashRequest(schema:BaseModel)-> str:

   # dump() schema: dict
   schema_dict = schema.model_dump(mode=json)
   # dumps()  dict to json with, parameter, sort_keys,and seperators
   schema_json = json.dumps(schema_dict,
              sort_keys=True,
              seperators=(",",":")

   )
   # hashhhhhhh the schema
   request_hash = hashlib.sha256(schema_json.encode('utf-8')).hexdigest()

   return request_hash



