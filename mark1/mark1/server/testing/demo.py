"""Scripted HTTP walkthrough of A's backend, using only generated fictional input."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from fastapi.testclient import TestClient
from PIL import Image

from ..app import create_app
from ..config import Settings


def main():
    with TemporaryDirectory(prefix="mark1-demo-") as directory:
        app = create_app(Settings(database=Path(directory) / "demo.sqlite"))
        token = app.state.service.store.issue_token()
        with TestClient(app) as client:
            client.headers["Authorization"] = "Bearer " + token
            response = client.post("/v2/sessions", headers={"Idempotency-Key": "demo-create"},
                                   json={"workflow_id": "demo-laptop-no-power", "symptom_code": "NO_POWER"})
            response.raise_for_status()
            session = response.json()

            def settle():
                nonlocal session
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    result = client.get("/v2/sessions/" + session["session_id"])
                    result.raise_for_status()
                    session = result.json()
                    if session["status"] != "EVALUATING":
                        print(session["status"])
                        return
                    time.sleep(0.01)
                raise RuntimeError("Demo inference did not finish")

            def send(operation, body):
                nonlocal session
                result = client.post(f"/v2/sessions/{session['session_id']}/{operation}",
                                     headers={"Idempotency-Key": f"demo-{operation}-{session['revision']}"},
                                     json={"expected_revision": session["revision"], **body})
                result.raise_for_status()
                session = result.json()
                settle()

            def observe(value):
                check = session["current_check"]
                send("observations", {"check_id": check["check_id"], "check_version": check["version"],
                                      "observation_code": check["observation_code"], "value": value, "human_confirmed": True})

            print("Synthetic local backend demo; no image perception or real repair is performed.")
            send("identity-candidates", {"manual_label": "DEMO-LAPTOP"})
            send("identity-confirmation", {"model_id": "DEMO-LAPTOP", "configuration_id": "DEMO-C1", "human_confirmed": True})
            observe("CLEAR")
            frame = BytesIO()
            Image.new("RGB", (160, 120), (40, 80, 120)).save(frame, "PNG")
            upload = client.post(f"/v2/sessions/{session['session_id']}/images", headers={"Idempotency-Key": "demo-frame"},
                                 data={"expected_revision": session["revision"], "purpose": "investigation"},
                                 files={"file": ("fictional.png", frame.getvalue(), "image/png")})
            upload.raise_for_status()
            settle()
            interaction = session["interaction"]
            binding = {k: interaction[k] for k in ("interaction_id", "template_id", "template_version")}
            send("view-responses", dict(binding, result="IMAGE", image_id=upload.json()["image_id"], human_confirmed=True))
            interaction = session["interaction"]
            binding = {k: interaction[k] for k in ("interaction_id", "template_id", "template_version")}
            send("answers", dict(binding, value="NO", human_confirmed=True))
            observe("OFF")
            assert session["status"] == "EXPLAINING"
            print("Advisory diagram:", session["interaction"]["diagram"]["diagram_id"])
            print("Suspected node:", session["interaction"]["highlights"][0]["node_id"])
            interaction = session["interaction"]
            binding = {k: interaction[k] for k in ("interaction_id", "template_id", "template_version")}
            send("explanation-acks", dict(binding, acknowledged=True))
            assert session["status"] == "ESCALATED"
            events = client.get(f"/v2/sessions/{session['session_id']}/events").json()["events"]
            print(f"Recorded {len(events)} durable events. No verified repair is claimed.")


if __name__ == "__main__":
    main()
