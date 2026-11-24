import json
import hashlib
from pydantic import BaseModel



def hashRequest(schema:BaseModel)-> str:

   # dump() schema: dict
   schema_dict = schema.model_dump(mode="json")  # // turn to python dictionary, with json compatible representaions
   print(f'From pydantic object to a dictionary: {schema_dict}.')
   # dumps()  dict to json with, parameter, sort_keys,and seperators
   schema_json = json.dumps(schema_dict,
              sort_keys=True,
              separators=(",",":")

   )
   # hashhhhhhh the schema
   request_hash = hashlib.sha256(schema_json.encode('utf-8')).hexdigest()

   return request_hash



