#!/bin/bash
# ============================================================
# PX4 SITL Parameter Overrides
# ============================================================
# Exports PX4_PARAM_* environment variables that PX4's rcS
# startup script reads to override default parameters.
#
# Source this BEFORE running `make px4_sitl`:
#   source config/px4_params/sitl_overrides.sh
#   cd $PX4_HOME && make px4_sitl gz_x500
# ============================================================

# === RC Loss (disabled — no RC transmitter in simulation) ===
export PX4_PARAM_NAV_RCL_ACT=0          # 0 = Disabled (no action on RC loss)
export PX4_PARAM_COM_RCL_EXCEPT=4        # 4 = Ignore RC loss in all modes

# === Data Link / GCS (disabled — no QGroundControl required) ===
export PX4_PARAM_NAV_DLL_ACT=0           # 0 = Disabled (no action on GCS loss)
export PX4_PARAM_COM_DL_LOSS_T=10        # 10s timeout before declaring DL loss

# === Geofence ===
export PX4_PARAM_GF_ACTION=1             # 1 = Warning on geofence breach
export PX4_PARAM_GF_MAX_HOR_DIST=500     # 500m horizontal geofence
export PX4_PARAM_GF_MAX_VER_DIST=120     # 120m vertical geofence

# === Offboard Control ===
export PX4_PARAM_COM_OF_LOSS_T=1.0       # 1s offboard loss timeout
export PX4_PARAM_COM_OBL_ACT=1           # 1 = Land on offboard loss

# === Battery Failsafe (simulated) ===
export PX4_PARAM_BAT_LOW_THR=0.20        # 20% low battery warning
export PX4_PARAM_BAT_CRIT_THR=0.10       # 10% critical battery
export PX4_PARAM_BAT_EMERGEN_THR=0.05    # 5% emergency battery

# === Return to Launch ===
export PX4_PARAM_RTL_RETURN_ALT=30       # 30m RTL return altitude
export PX4_PARAM_RTL_DESCEND_ALT=10      # 10m RTL descend altitude
export PX4_PARAM_RTL_LAND_DELAY=5        # 5s delay before landing at RTL

# === Mission ===
export PX4_PARAM_MIS_TAKEOFF_ALT=15.0    # 15m default takeoff altitude
export PX4_PARAM_NAV_ACC_RAD=2.0         # 2m waypoint acceptance radius

echo "[sitl_overrides] PX4 SITL parameters exported (GCS/RC checks disabled)"
