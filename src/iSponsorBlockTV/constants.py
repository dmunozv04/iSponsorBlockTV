userAgent = "iSponsorBlockTV/0.1"
SponsorBlock_service = "youtube"
SponsorBlock_actiontype = "skip"

Youtube_api = "https://www.googleapis.com/youtube/v3/"

skip_categories = (
    ("Sponsor", "sponsor"),
    ("Self Promotion", "selfpromo"),
    ("Intro", "intro"),
    ("Outro", "outro"),
    ("Music Offtopic", "music_offtopic"),
    ("Interaction", "interaction"),
    ("Exclusive Access", "exclusive_access"),
    ("POI Highlight", "poi_highlight"),
    ("Preview", "preview"),
    ("Filler", "filler"),
)

youtube_client_blacklist = ["TVHTML5_FOR_KIDS"]

config_file_blacklist_keys = ["config_file", "data_dir"]
