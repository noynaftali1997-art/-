from .apify import ApifyFacebookGroups, ApifyInstagramHashtags
from .google import GoogleCSE, Serper
from .reddit import Reddit
from .rss import RSS

ALL_SOURCES = {
    "serper": Serper,
    "google_cse": GoogleCSE,
    "apify_facebook_groups": ApifyFacebookGroups,
    "apify_instagram_hashtags": ApifyInstagramHashtags,
    "reddit": Reddit,
    "rss": RSS,
}
