"""Streamlit UI for VLM_Eval — interactive Seed vs Gemini comparison + batch report.

Run:  streamlit run app.py
Keys are read from .env (see .env.example). Nothing is committed or logged.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from vlm_eval.config import all_providers, judge_provider_name
from vlm_eval.providers import ChatClient
from vlm_eval.report import render as render_report
from vlm_eval.runner import DIRECTOR_METRICS, load_dataset, run
from vlm_eval.tasks import get_task
from vlm_eval.tasks.director3d import score_director

ROOT = Path(__file__).resolve().parent
DATASETS = {
    "director3d": ROOT / "datasets/director3d/manifest.json",
    "general": ROOT / "datasets/general/manifest.json",
}

st.set_page_config(page_title="Seed vs Gemini · VLM Eval", layout="wide")


# --------------------------------------------------------------------------- #
# Sidebar: provider status
# --------------------------------------------------------------------------- #
cfgs = all_providers()
st.sidebar.title("VLM Eval")
st.sidebar.caption("BytePlus Seed 2.1 vs Google Gemini 3.1")
st.sidebar.subheader("Providers")
for name, cfg in cfgs.items():
    if cfg.configured:
        st.sidebar.success(f"{name}: {cfg.model}")
    else:
        st.sidebar.error(f"{name}: not configured")
st.sidebar.caption("Configure keys in `.env` (copy from `.env.example`).")

use_mock = st.sidebar.toggle("Offline mock mode (no API calls)", value=False,
                             help="Use scripted mock responses to explore the UI without keys.")


def build_client(cfg):
    if use_mock:
        from tests.mock_client import MockClient
        return MockClient(cfg)
    return ChatClient(cfg)


def clients_dict():
    return {name: build_client(cfg) for name, cfg in cfgs.items()}


tab_compare, tab_batch = st.tabs(["🔍 Compare (interactive)", "📊 Batch report"])


# --------------------------------------------------------------------------- #
# Compare tab
# --------------------------------------------------------------------------- #
with tab_compare:
    st.subheader("Side-by-side comparison")
    left, right = st.columns([1, 1])

    with left:
        source = st.radio("Image source", ["Dataset sample", "Upload"], horizontal=True)
        image_path = None
        item = None
        if source == "Dataset sample":
            ds = st.selectbox("Dataset", list(DATASETS))
            items = load_dataset(DATASETS[ds])
            item = st.selectbox("Item", items, format_func=lambda it: f"{it.id}  ({it.task})")
            image_path = item.image_path
        else:
            up = st.file_uploader("Image", type=["png", "jpg", "jpeg", "webp"])
            if up:
                tmp = Path(tempfile.gettempdir()) / f"vlme_{up.name}"
                tmp.write_bytes(up.getbuffer())
                image_path = str(tmp)

        default_prompt = ""
        if item is not None:
            try:
                default_prompt = item.prompt or get_task(item.task).default_prompt(item)
            except Exception:
                default_prompt = ""
        prompt = st.text_area("Prompt", value=default_prompt, height=160,
                              placeholder="Ask something about the image…")
        expect_json = st.checkbox("Expect JSON (parse + retry)",
                                  value=(item.task == "director3d" if item else False))
        run_btn = st.button("Run both models", type="primary", use_container_width=True)

        if image_path:
            st.image(image_path, caption=Path(image_path).name, use_container_width=True)

    with right:
        if run_btn and image_path and prompt.strip():
            cols = st.columns(len(cfgs))
            for col, (name, cfg) in zip(cols, cfgs.items()):
                with col:
                    st.markdown(f"**{cfg.model}**")
                    if not cfg.configured and not use_mock:
                        st.warning("Not configured")
                        continue
                    client = build_client(cfg)
                    with st.spinner(f"{name}…"):
                        res = client.chat(prompt, image_paths=[image_path],
                                          expect_json=expect_json, json_object=expect_json,
                                          max_tokens=1500)
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Latency", f"{res.latency_s:.1f}s")
                    c2.metric("Attempts", res.attempts)
                    c3.metric("JSON", "✓" if (res.json_valid or not expect_json and res.ok) else "✗")
                    if not res.ok:
                        st.error(res.error or "call failed")
                    st.text_area("Answer", value=res.text or "(empty)", height=220, key=f"ans_{name}")

                    # If this is a director3d dataset item, score it live.
                    if item is not None and item.task == "director3d" and res.json_valid:
                        metrics, notes = score_director(res.json_obj, item.ground_truth)
                        scored = [metrics[k] for k in metrics if metrics[k] is not None]
                        comp = sum(scored) / len(scored) if scored else None
                        st.caption(f"Composite vs GT: **{comp:.2f}**" if comp is not None else "—")
                        st.json({k: (round(v, 2) if v is not None else None)
                                 for k, v in metrics.items()}, expanded=False)
                        if notes:
                            st.caption("Flags: " + ", ".join(notes))
        else:
            st.info("Pick or upload an image, enter a prompt, then **Run both models**.")


# --------------------------------------------------------------------------- #
# Batch tab
# --------------------------------------------------------------------------- #
with tab_batch:
    st.subheader("Run a dataset and generate the report")
    c1, c2, c3 = st.columns([2, 1, 1])
    ds_choice = c1.multiselect("Datasets", list(DATASETS), default=list(DATASETS))
    repeats = c2.number_input("Repeats", 1, 10, 3)
    go = c3.button("Run eval", type="primary", use_container_width=True)

    if go:
        if not ds_choice:
            st.warning("Select at least one dataset.")
        elif not use_mock and not all(cfgs[n].configured for n in cfgs):
            st.error("Not all providers configured. Add keys to `.env` or enable mock mode.")
        else:
            items = []
            for ds in ds_choice:
                items.extend(load_dataset(DATASETS[ds]))
            judge = None
            jname = judge_provider_name()
            if jname in cfgs:
                judge = build_client(cfgs[jname])
            bar = st.progress(0.0, text="Starting…")
            total = len(items) * len(cfgs) * repeats
            state = {"n": 0}

            def prog(msg):
                state["n"] += 1
                bar.progress(min(1.0, state["n"] / total), text=msg)

            results = run(cfgs, items, repeats=int(repeats), judge_client=judge,
                          clients=clients_dict() if use_mock else None, progress=prog)
            bar.progress(1.0, text="Done")

            st.success("Leaderboard")
            st.table([
                {"Provider": r["label"], "Composite": round(r["composite"], 2),
                 "JSON %": round(r["json_rate"] * 100), "lat med": round(r["lat_med"], 1)}
                for r in results["leaderboard"]
            ])
            html = render_report(results)
            st.download_button("⬇ Download HTML report", data=html,
                               file_name="vlm_eval_report.html", mime="text/html")
            components.html(html, height=900, scrolling=True)
