"""One valid example instance per contract (used by round-trip and schema tests)."""

from __future__ import annotations

from cosmic_triage import contracts as C

PT = C.PhotometryPoint(mjd=60760.3, band="r", is_detection=True, mag=18.2, mag_err=0.05, drb=0.99, isdiffpos=True,
                       candid="123")
UL = C.PhotometryPoint(mjd=60758.3, band="g", is_detection=False, limiting_mag=20.4)
CTX = C.CandidateContext(ra=197.336, dec=46.24, gal_b=70.4, sgscore1=0.02, distpsnr1=5.1, srmag1=19.9)
FR = C.FinkAlertRow(mjd=60760.3, candid="123", rf_snia_vs_nonia=0.0, snn_snia_vs_nonia=0.66, snn_sn_vs_all=0.8,
                    cdsxmatch="Unknown", tns_alert_time="")
SP = C.StampPrior(first_alert_mjd=60758.3, classifier_version="stamp_classifier_1.0.4", probs={"SN": 0.7, "AGN": 0.1})
CS = C.CandidateState(oid="ZTF25aaafbbk", t_mjd=60761.0, context=CTX, photometry=(UL, PT), fink_rows=(FR,),
                      stamp_prior=SP, first_detection_mjd=60760.3, last_detection_mjd=60760.3, n_detections=1,
                      n_nondetections=1, brightest_mag=18.2, latest_mag=18.2, latest_band="r")
SNAP = C.Snapshot(t_mjd=60761.0, night_id="2025-03-26", candidates=(CS,), pool_config_hash="abc",
                  denylist_version="1.0", sources={"alerce": "ztf/v1"})
BEL = C.Belief(oid="ZTF25aaafbbk", t_mjd=60761.0,
               probs={"Ia": 0.6, "II": 0.2, "Ibc": 0.1, "other_luminous": 0.05, "contaminant": 0.05},
               channel_logp={"fink": {"Ia": -0.5}}, entropy_nats=1.15, phase_days=-5.0, config_hash="h")
OBJ = C.Objective(id="O1", name="Cosmology-grade SNe Ia", description="pre-peak Ia spectra",
                  reward_table="configs/objectives/O1.yaml")
RT = C.RewardTable(version="1.0", objective="O1", phase_bins=("pre", "post"),
                   rewards={"Ia": {"pre": 1.0, "post": 0.3}, "contaminant": {"pre": 0.0, "post": 0.0}})
ACT = C.Action(kind="spectrum", oid="ZTF25aaafbbk", instrument="sedm_like", exposure_s=1800, expected_reward=0.6)
SO = C.ScheduledObservation(oid="ZTF25aaafbbk", action="spectrum", start_mjd=60761.2, end_mjd=60761.23,
                            exposure_s=1800, overhead_s=300)
SCH = C.Schedule(night_id="2025-03-26", facility_id="palomar_sedm", budget=4, items=(SO,), solver="cpsat",
                 solver_status="OPTIMAL", objective_value=0.6, config_hash="h")
OUT = C.Outcome(oid="ZTF25aaafbbk", night_id="2025-03-26", action="spectrum", realized_reward=1.0,
                revealed_class="Ia", sim_level="L0", simulated=False, source="bts_truth")
EV = C.Evidence(id="ev1", source="sherlock", source_date=None, retrieved_at_sim_time=60761.0,
                query={"oid": "ZTF25aaafbbk"}, raw_excerpt_hash="deadbeef", parsed={"z": 0.036})
VC = C.ValidationCheck(name="date_le_t", passed=True)
VR = C.ValidationReport(accepted=True, checks=(VC,), support_score=0.9)
CD = C.ClaimDraft(kind="host_redshift", payload={"z": 0.036}, evidence_ids=("ev1",), extractor_model="claude-x")
CL = C.Claim(kind="host_redshift", payload={"z": 0.036}, evidence_ids=("ev1",), extractor_model="claude-x",
             validation=VR)
CMP = C.Compaction(id="c1", created_at_sim_time=60761.0, summary="host z=0.036 [ev1]", cited_ids=("ev1",))
LED = C.EvidenceLedger(oid="ZTF25aaafbbk", entries=(EV,), claims=(CL,), compactions=(CMP,), version="1")
SPAN = C.Span(span_id="s1", kind="tool", name="sherlock", latency_ms=12.0, cache_hit=True, attrs={"n": 1})
TR = C.Trace(run_id="r1", oid="ZTF25aaafbbk", t_mjd=60761.0, config_version="h", mode="exploratory", spans=(SPAN,),
             cost_usd=0.0, model_ids={})
AV = C.ActionValue(kind="spectrum", value=0.6, components={"Ia": 0.6})
DT = C.DecisionTrace(run_id="r1", night_id="2025-03-26", oid="ZTF25aaafbbk", t_mjd=60761.0, belief_top="Ia",
                     considered=(AV,), chosen="spectrum", reason="highest expected reward", why_not={"wait": "lower"})
RC = C.RunConfig(run_id="r1", mode="bench", seed=1, config_hash="h", config_hashes={"prefilter": "a"},
                 model_ids={}, code_version="abc", script="test")
RM = C.RunManifest(config=RC, output_hash="ff", outputs={"x.json": "ff"})
MOON = C.MoonState(alt=10.0, az=120.0, phase=0.4)
FC = C.FrameCandidate(oid="ZTF25aaafbbk", alt=45.0, az=200.0, belief_top=None, is_real_detection_now=True)
FS = C.FacilityState()
TE = C.TheaterEvent(t_mjd=60761.2, kind="detection", ref_id="123", oid="ZTF25aaafbbk", sim_level="L0")
NF = C.NightFrame(t_mjd=60761.2, sun_alt=-30.0, sun_az=10.0, moon=MOON, twilight="night", candidates=(FC,),
                  facility=FS, events=(TE,))
TN = C.TheaterNight(run_id="r1", night_id="2025-03-26", mode="exploratory", config_hash="h", site_name="Palomar",
                    site_lat=33.36, site_lon=-116.87, site_height_m=1712.0, start_mjd=60761.0, end_mjd=60761.6,
                    cadence_min=5.0, n_frames=10, n_candidates=1, sunset_mjd=60761.1, sunrise_mjd=60761.55,
                    astro_dusk_mjd=60761.15, astro_dawn_mjd=60761.5)

EXAMPLES: dict[type, object] = {type(x): x for x in [
    PT, CTX, FR, SP, CS, SNAP, BEL, OBJ, RT, ACT, SO, SCH, OUT, EV, VC, VR, CD, CL, CMP, LED, SPAN, TR, AV, DT, RC, RM,
    MOON, FC, FS, TE, NF, TN,
]}
