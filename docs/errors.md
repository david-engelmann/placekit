# Errors

Every failure raises a subclass of `PlacesError`, carrying `status_code` and `google_status` when the error came from the API. The one exception is saving a downloaded photo, where `PhotoMedia.save` raises the `OSError` family for a path the filesystem refuses, by design. A save refused part way can leave a zero byte or partial file at the target, and an existing file is truncated before the write begins, so a refused save can leave the target shorter than the file it replaced.

Every `PlacesError` also carries a `kind` string naming its category, such as `auth`, `rate_limit` or `config`, for callers who would rather branch on a plain string than on the class. `ConfigError` is also a `ValueError`, so code that already catches `ValueError` for bad arguments catches it too.

Classification follows the Google envelope status first and the HTTP code second, so the exception class and `status_code` can come from different sources. A quota envelope on an HTTP 500 is a `RateLimitError` with `status_code` 500, and the `status_mismatch` attribute is True whenever the envelope code and the HTTP status disagree. API exceptions also carry `retryable`, which says whether a caller side retry can plausibly succeed, and `retry_after`, the seconds from a `Retry-After` header when the response sent one. Exceptions raised by a client call carry `context`, naming the call that failed, and failures from the address helpers and from field mask construction carry the helper name or the mask as their context the same way, with an address failure naming the innermost helper that raised it rather than the helper the caller invoked. Model decode errors carry no context of their own, and their messages name the model and the payload key instead. A decode failure reached through a client call still arrives carrying that call context, because the client attaches it the way it does for every error a call raises. API exceptions also carry the parsed envelope details, as `error_code` and `details` and `field_violations` and `quota_violations`, so a rejected request shows which fields it broke and which quota it hit.

| Exception | Raised when |
| --- | --- |
| `AuthenticationError` | The key was rejected or lacks permission, HTTP 401 or 403 |
| `RateLimitError` | Quota is exhausted or the rate limit is hit, HTTP 429 |
| `NotFoundError` | The resource does not exist, HTTP 404 |
| `InvalidRequestError` | The request was malformed, HTTP 400 |
| `ApiError` | A canonical Google status with no narrower class, such as deadline exceeded |
| `NetworkError` | No HTTP response was produced |
| `DecodeError` | A success body did not match the expected shape |
| `ConfigError` | The client was called incorrectly, detected before any request |

`QuotaError` is exported as an alias of `RateLimitError`, so either name catches a quota failure.

Local validation follows one coercion rule everywhere. Numbers must be real and finite, bools are never numbers, and strings are never lists, so a value of the wrong kind fails as a `ConfigError` before any request instead of being converted into something else on the wire.

```python
from placekit import Client, RateLimitError

client = Client("YOUR_API_KEY")
try:
    client.text_search("cafes in Sydney")
except RateLimitError as exc:
    print("quota", exc.status_code, exc.google_status)
```

