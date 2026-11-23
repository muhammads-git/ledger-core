from uuid import uuid4



def get_idempotency_key():
   return str(uuid4())

