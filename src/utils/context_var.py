import contextvars

request_id_var = contextvars.ContextVar("request_id", default=0)
