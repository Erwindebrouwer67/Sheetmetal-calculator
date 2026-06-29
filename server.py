"""
Inno Mechatronics — Plaatwerk STEP Analyser
Lokale server: ontvangt STEP-bestand, retourneert analyse als JSON.

Installatie:
    pip install cadquery flask flask-cors

Starten:
    python server.py

Server draait op http://localhost:5050
"""

import math
import tempfile
import os
from collections import defaultdict

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Staat verbinding toe vanuit de PWA (andere poort/origin)


def analyse_step(path: str) -> dict:
    import cadquery as cq
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    from OCP.TopoDS import TopoDS

    result = cq.importers.importStep(path)
    solid = result.solids().val()

    def iter_faces(solid):
        exp = TopExp_Explorer(solid.wrapped, TopAbs_FACE)
        while exp.More():
            yield TopoDS.Face_s(exp.Current())
            exp.Next()

    # ── Cilindrische faces → buigingen ───────────────────────────────────────
    cyl_data = []
    for face in iter_faces(solid):
        adaptor = BRepAdaptor_Surface(face)
        if adaptor.GetType() == GeomAbs_Cylinder:
            r = adaptor.Cylinder().Radius()
            u1, u2 = adaptor.FirstUParameter(), adaptor.LastUParameter()
            v1, v2 = adaptor.FirstVParameter(), adaptor.LastVParameter()
            angle_deg = round(math.degrees(abs(u2 - u1)), 1)
            length = round(abs(v2 - v1), 2)
            axis = adaptor.Cylinder().Axis().Direction()
            key = (
                abs(round(axis.X(), 1)),
                abs(round(axis.Y(), 1)),
                abs(round(axis.Z(), 1)),
            )
            cyl_data.append({"r": round(r, 3), "angle": angle_deg, "length": length, "axis": key})

    if not cyl_data:
        return {"error": "Geen buigingen gevonden — is dit een plaatwerk onderdeel?"}

    inner_r = min(c["r"] for c in cyl_data)
    outer_r = max(c["r"] for c in cyl_data)
    mat_t = round(outer_r - inner_r, 2)
    k = 0.33
    ba = math.radians(90) * (inner_r + k * mat_t)

    # Buigingen per as-richting
    bend_groups = defaultdict(list)
    for c in cyl_data:
        bend_groups[c["axis"]].append(c)

    bends = []
    for axis_key, faces in bend_groups.items():
        inner_faces = [f for f in faces if f["r"] == inner_r]
        for f in inner_faces:
            bends.append({"angle": f["angle"], "length": f["length"]})

    # ── Vlakke faces → armlengtes ─────────────────────────────────────────────
    plane_faces = []
    for face in iter_faces(solid):
        adaptor = BRepAdaptor_Surface(face)
        if adaptor.GetType() == GeomAbs_Plane:
            props = GProp_GProps()
            BRepGProp.SurfaceProperties_s(face, props)
            area = props.Mass()
            n = adaptor.Plane().Axis().Direction()
            cq_face = cq.Face(face)
            bb = cq_face.BoundingBox()
            plane_faces.append({
                "area": round(area, 1),
                "nz": round(abs(n.Z()), 2),
                "ny": round(abs(n.Y()), 2),
                "nx": round(abs(n.X()), 2),
                "dx": round(bb.xmax - bb.xmin, 2),
                "dy": round(bb.ymax - bb.ymin, 2),
                "dz": round(bb.zmax - bb.zmin, 2),
            })

    plane_faces.sort(key=lambda f: f["area"], reverse=True)

    bodem_face   = next((f for f in plane_faces if f["nz"] > 0.9), None)
    zijwand_face = next((f for f in plane_faces if f["ny"] > 0.9), None)
    flens_face   = next(
        (f for f in plane_faces if f["nz"] > 0.9 and bodem_face and f["area"] < bodem_face["area"] * 0.5),
        None,
    )

    arm_bodem   = bodem_face["dy"]   if bodem_face   else 0
    arm_zijwand = zijwand_face["dz"] if zijwand_face else 0
    arm_flens   = flens_face["dy"]   if flens_face   else 0
    breedte     = bodem_face["dx"]   if bodem_face   else 0

    # Aantal buigingen bepaalt hoeveel BA's erbij
    n_bends = len(bends)
    lengte_ontvouwd = round(arm_flens + arm_zijwand + arm_bodem + n_bends * ba, 1)
    snijlengte = round(2 * (breedte + lengte_ontvouwd), 1)

    # Gaten detecteren: cilindrische faces met diepte ≈ plaatdikte
    gaten = []
    for face in iter_faces(solid):
        adaptor = BRepAdaptor_Surface(face)
        if adaptor.GetType() == GeomAbs_Cylinder:
            r = adaptor.Cylinder().Radius()
            u1, u2 = adaptor.FirstUParameter(), adaptor.LastUParameter()
            v1, v2 = adaptor.FirstVParameter(), adaptor.LastVParameter()
            angle_deg = math.degrees(abs(u2 - u1))
            depth = abs(v2 - v1)
            # Gat = volledige cilinder (360°) met diepte ≈ plaatdikte
            if abs(angle_deg - 360) < 5 and abs(depth - mat_t) < mat_t * 0.5:
                gaten.append({"diameter": round(r * 2, 2)})

    insteekpunten = len(gaten) + 1  # gaten + buitencontour

    return {
        "bestandsnaam": os.path.basename(path),
        "materiaaldikte": mat_t,
        "inner_buigradius": inner_r,
        "snijlengte": snijlengte,
        "insteekpunten": insteekpunten,
        "aantal_buigingen": n_bends,
        "buigingen": bends,
        "gaten": gaten,
        "ontvouwd": {
            "breedte": breedte,
            "lengte": lengte_ontvouwd,
            "arm_bodem": arm_bodem,
            "arm_zijwand": arm_zijwand,
            "arm_flens": arm_flens,
            "buigtoevoeging": round(ba, 3),
        },
    }


@app.route("/analyse", methods=["POST"])
def analyse():
    if "file" not in request.files:
        return jsonify({"error": "Geen bestand meegestuurd"}), 400

    f = request.files["file"]
    if not f.filename.lower().endswith((".step", ".stp")):
        return jsonify({"error": "Alleen .step of .stp bestanden worden ondersteund"}), 400

    # Sla tijdelijk op
    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        data = analyse_step(tmp_path)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Analyse mislukt: {str(e)}"}), 500
    finally:
        os.unlink(tmp_path)


@app.route("/status", methods=["GET"])
def status():
    return jsonify({"status": "ok", "versie": "1.0", "naam": "Inno Plaatwerk Analyser"})


if __name__ == "__main__":
    print("=" * 55)
    print("  Inno Mechatronics — Plaatwerk STEP Analyser")
    print("  Server draait op http://localhost:5050")
    print("  Open de PWA en upload een STEP-bestand.")
    print("=" * 55)
    app.run(host="0.0.0.0", port=5050, debug=False)
