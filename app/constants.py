import os

from app.config import BASE_DIR

# --- Shift types (the ``type`` field on the schedule table) -----------------
TYPE_CLEANING = "cleaning"
TYPE_CLEANING_CATLOFT = "cleaning_catloft"
TYPE_MEDICAL = "medical"
TYPE_STERIL_ACCEPTANCE = "steril_acceptance"
TYPE_STERIL_RELEASE = "steril_release"

SCHEDULE_TYPES = [
    TYPE_CLEANING,
    TYPE_MEDICAL,
    TYPE_STERIL_ACCEPTANCE,
    TYPE_STERIL_RELEASE,
    TYPE_CLEANING_CATLOFT,
]

# --- Volunteer duty codes (the ``duty_codes`` lookup on the volunteer table) -
DUTY_CLEANING = "kk_cleaning"
DUTY_MEDICAL = "kk_medical"
DUTY_STERIL = "steril_cat_in_out"
DUTY_ADMIN_CURATOR = "kk_admin_curator"

# Short codes packed into callback data for the "sign up" flow.
DUTY_SHORT_CLEANING = "cln"
DUTY_SHORT_MEDICAL = "med"
DUTY_SHORT_STERIL = "steril"

# --- Scheduling windows -----------------------------------------------------
# Number of days ahead a volunteer can sign up for.
SCHEDULE_WINDOW_DAYS = 14

# --- Cat-flat (sterilization base) ------------------------------------------
CAT_FLAT_TABLE = "cat_flat_fostering"

# Statuses that mean a cat is currently in the cat flat.
CAT_FLAT_STATUSES = [
    "принята в кд",
    "ожидает стерилизацию",
    "готова к выписке",
    "назначен медуход",
]

# Emoji-named checkbox fields — these strings must match Airtable exactly.
FIELD_MED_CARE = "💊 med_care"
FIELD_IS_DEFLEAD = "🦟is_deflead"
FIELD_IS_VACCINATED = "💉is_vaccinated"
FIELD_IS_DEWORMED = "𓆑is_dewormed"

# Room capacities used for the occupancy percentages in the overview.
ROOM_CAPACITIES = {"K1": 10, "K2": 10, "Hall": 4}

# Fallback grouping label for cats with no room set (also used as a group key).
NO_ROOM = "Без комнаты"

# Traffic-light thresholds (days a cat has spent in the flat).
DAYS_GREEN_THRESHOLD = 7
DAYS_YELLOW_THRESHOLD = 30

# Sentinel used to sort cats with an unknown arrival date to the end.
UNKNOWN_DAYS_SORT_KEY = 999999

# Airtable formulas have a length limit, so departed-cat lookups are chunked.
DEPARTED_FETCH_CHUNK_SIZE = 25

# Snapshot of the previous cat-flat state, kept next to the code (not the CWD).
CAT_FLAT_STATE_FILE = os.path.join(BASE_DIR, "cat_flat_state.json")

# --- Softr deep links -------------------------------------------------------
SOFTR_REQUEST_DETAILS_URL = "https://catebi.softr.app/sterilization-request-details?recordId={}"
SOFTR_CAT_FLAT_DETAILS_URL = "https://catebi.softr.app/cat-flat-fostering-details?recordId={}"

# --- Telegram supergroup ids ------------------------------------------------
# Supergroup chat ids are stored without the "-100" prefix in the settings table.
SUPERGROUP_ID_PREFIX = "-100"
