import json
import os
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = os.environ.get("INCIDENT_OS_URL", "http://localhost:8000")

TIMEOUT_S = 30


class ApiError(Exception):
    def __init__(self, status: int, detail):
        self.status = status
        self.detail = detail
        message = f"API error {status}"
        if isinstance(detail, dict):
            message += f": {detail.get('detail') or detail.get('message') or detail}"
        elif detail is not None:
            message += f": {detail}"
        super().__init__(message)


class Api:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body=None, params=None):
        if params:
            path = path + "?" + urllib.parse.urlencode(params)
        url = self.base_url + path
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = None
            try:
                detail = json.loads(exc.read())
            except Exception:
                detail = exc.reason
            raise ApiError(exc.code, detail) from None

    def health(self):
        return self._request("GET", "/api/v1/health")

    def list_incidents(self, service=None, status=None, limit=100):
        params = {"limit": limit}
        if service:
            params["service"] = service
        if status:
            params["status"] = status
        return self._request("GET", "/api/v1/incidents", params=params)

    def get_incident(self, incident_id: str):
        return self._request("GET", f"/api/v1/incidents/{incident_id}")

    def investigate(self, incident_id: str):
        return self._request("POST", f"/api/v1/incidents/{incident_id}/investigate")

    def resolve_incident(self, incident_id: str):
        return self._request("POST", f"/api/v1/incidents/{incident_id}/resolve")

    def clear_incidents(self, service=None, status=None):
        params = {}
        if service:
            params["service"] = service
        if status:
            params["status"] = status
        return self._request("DELETE", "/api/v1/incidents", params=params)

    def get_investigation(self, investigation_id: str):
        return self._request("GET", f"/api/v1/investigations/{investigation_id}")

    def list_incident_investigations(self, incident_id: str):
        return self._request("GET", f"/api/v1/incidents/{incident_id}/investigations")

    def evidence(self, investigation_id: str):
        return self._request("GET", f"/api/v1/investigations/{investigation_id}/evidence")

    def candidates(self, investigation_id: str):
        return self._request("GET", f"/api/v1/investigations/{investigation_id}/candidates")

    def root_cause(self, investigation_id: str):
        return self._request("GET", f"/api/v1/investigations/{investigation_id}/root-cause")

    def resolve_incident_id(self, incident_id: str) -> str:
        if len(incident_id) == 36 and "-" in incident_id:
            return incident_id
        incidents = self.list_incidents(limit=1000)
        matches = [i["id"] for i in incidents if i["id"].startswith(incident_id)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ApiError(0, f"ambiguous incident id prefix {incident_id!r}")
        raise ApiError(404, {"detail": f"no incident matches {incident_id!r}"})
