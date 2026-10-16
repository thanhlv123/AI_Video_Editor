from pathlib import Path
from collections import Counter
import json
import re
import sys


# ==================================================
# PROJECT ROOT
# ==================================================

ROOT = Path(
    r"D:\YouTubeTools\AI_Video_Editor"
)

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from pipeline.context_geo import (
    enrich_manifest_with_project_context,
)


# ==================================================
# TEST MANIFEST
# ==================================================

MANIFEST = (
    ROOT
    / "projects"
    / "runs"
    / "file_chay_thu_01_1356b5b5"
    / "ai_manifest.json"
)


# ==================================================
# GEO POLICIES
# ==================================================

STRICT = "STRICT"
REGIONAL_PROXY = "REGIONAL_PROXY"
VISUAL_PROXY = "VISUAL_PROXY"
GENERIC = "GENERIC"


# ==================================================
# REGIONAL VISUAL PROFILES
#
# These do NOT mean countries are identical.
# They are only retrieval expansion groups.
# ==================================================

REGIONAL_PROFILES = {

    "morocco": {
        "display": "Morocco",

        "regions": [
            "North Africa",
            "Maghreb",
            "Mediterranean",
        ],

        "proxy_countries": [
            "Algeria",
            "Tunisia",
        ],

        "visual_terms": [
            "North African",
            "Maghreb",
            "Mediterranean",
            "warm dry climate",
            "arid landscape",
        ],
    },

    "serbia": {
        "display": "Serbia",

        "regions": [
            "Balkans",
            "Southeast Europe",
            "Eastern Europe",
        ],

        "proxy_countries": [
            "Bosnia and Herzegovina",
            "Montenegro",
            "North Macedonia",
            "Croatia",
            "Bulgaria",
        ],

        "visual_terms": [
            "Balkan",
            "Southeast European",
            "continental European",
        ],
    },

    "vietnam": {
        "display": "Vietnam",

        "regions": [
            "Southeast Asia",
            "Tropical Asia",
        ],

        "proxy_countries": [
            "Thailand",
            "Laos",
            "Cambodia",
            "Malaysia",
            "Indonesia",
        ],

        "visual_terms": [
            "Southeast Asian",
            "tropical rural",
            "humid tropical",
        ],
    },

    "japan": {
        "display": "Japan",

        "regions": [
            "East Asia",
        ],

        "proxy_countries": [
            "South Korea",
        ],

        "visual_terms": [
            "East Asian",
            "modern dense city",
        ],
    },
}


# ==================================================
# EXPLICIT PLACE TERMS
#
# If these appear clearly in CURRENT dialogue or
# AI's exact search target, geography is important.
# ==================================================

EXPLICIT_PLACES = {

    # Morocco
    "casablanca",
    "marrakech",
    "marrakesh",
    "rabat",
    "fes",
    "fez",
    "tangier",
    "agadir",
    "meknes",
    "essaouira",
    "chefchaouen",
    "atlas mountains",
    "strait of gibraltar",

    # Serbia
    "belgrade",
    "beograd",
    "novi sad",

    # Common world landmarks / locations
    "eiffel tower",
    "times square",
    "burj khalifa",
    "mount fuji",
    "grand canyon",
    "big ben",
    "colosseum",
    "sydney opera house",
}


# ==================================================
# BROAD GEO TERMS
# ==================================================

BROAD_GEO_TERMS = {

    "north africa",
    "maghreb",
    "mediterranean",
    "africa",
    "balkans",
    "balkan",
    "southeast europe",
    "eastern europe",
    "southeast asia",
    "east asia",
    "middle east",
    "rural",
    "village",
    "mountain",
    "mountains",
    "desert",
    "coastline",
    "coastal",
    "countryside",
}


# ==================================================
# HUMAN / DAILY LIFE / GENERIC VISUAL TERMS
# ==================================================

VISUAL_PROXY_TERMS = {

    "people",
    "person",
    "woman",
    "women",
    "man",
    "men",
    "family",
    "student",
    "students",
    "farmer",
    "farmers",
    "worker",
    "workers",

    "walking",
    "working",
    "shopping",
    "eating",
    "drinking",
    "using phone",
    "smartphone",
    "social media",
    "university",

    "street",
    "market",
    "home",
    "house",
    "apartment",
    "farm",
    "vineyard",
    "grapevines",
    "agriculture",
    "clothing",
    "fashion",
    "daily life",
    "lifestyle",
}


# ==================================================
# TEXT HELPERS
# ==================================================

def clean_text(value):

    return str(
        value
        or ""
    ).strip()


def normalized(value):

    return (
        clean_text(value)
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )


def contains_term(
    text,
    terms,
):

    text = normalized(
        text
    )

    for term in terms:

        if normalized(
            term
        ) in text:

            return True

    return False


# ==================================================
# DETECT A SPECIFIC NAMED GEOGRAPHIC FEATURE
# ==================================================

def detect_named_geo_feature(
    text,
):

    text = clean_text(
        text
    )


    # Examples:
    #
    # Atlas Mountains
    # Nile River
    # Red Sea
    # Sahara Desert
    # Lake Bled
    # Strait of Gibraltar

    patterns = [

        r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s+Mountains\b",

        r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s+River\b",

        r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s+Sea\b",

        r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s+Desert\b",

        r"\bLake\s+[A-Z][A-Za-z]+\b",

        r"\bStrait\s+of\s+[A-Z][A-Za-z]+\b",

        r"\bMount\s+[A-Z][A-Za-z]+\b",
    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            text,
        )

        if match:

            return match.group(
                0
            )


    return None


# ==================================================
# EXPLICIT PLACE DETECTION
# ==================================================

def find_explicit_place(
    dialogue,
    primary_keyword,
):

    combined = (
        clean_text(dialogue)
        + " "
        + clean_text(primary_keyword)
    )


    lower = normalized(
        combined
    )


    for place in sorted(
        EXPLICIT_PLACES,
        key=len,
        reverse=True,
    ):

        if place in lower:

            return place


    named_feature = (
        detect_named_geo_feature(
            combined
        )
    )


    if named_feature:

        return named_feature


    return None


# ==================================================
# CHECK IF COUNTRY ITSELF IS THE VISUAL SUBJECT
# ==================================================

def country_is_visual_subject(
    dialogue,
    project_country,
    analysis,
):

    if not project_country:

        return False


    dialogue_lower = normalized(
        dialogue
    )

    country_lower = normalized(
        project_country
    )


    if (
        country_lower
        not in dialogue_lower
    ):

        return False


    subject = normalized(
        analysis.get(
            "subject",
            ""
        )
    )


    context = normalized(
        analysis.get(
            "context",
            ""
        )
    )


    strict_country_cues = [

        "this is " + country_lower,

        "map",
        "geographic",
        "border",
        "coastline",
        "separated from",
        "country overview",
        "aerial",
    ]


    combined = (
        dialogue_lower
        + " "
        + subject
        + " "
        + context
    )


    return any(
        cue in combined

        for cue
        in strict_country_cues
    )


# ==================================================
# CLASSIFY GEO POLICY
# ==================================================

def classify_geo_policy(
    scene,
):

    dialogue = clean_text(
        scene.get(
            "dialogue",
            ""
        )
    )


    analysis = scene.get(
        "analysis",
        {},
    )


    search = scene.get(
        "search",
        {},
    )


    project_context = scene.get(
        "project_context",
        {},
    )


    project_country = (
        project_context.get(
            "required_country"
        )
    )


    primary_keyword = clean_text(
        search.get(
            "primary_keyword",
            ""
        )
    )


    # ----------------------------------------------
    # 1. EXPLICIT NAMED LOCATION / LANDMARK
    # ----------------------------------------------

    explicit_place = (
        find_explicit_place(
            dialogue,
            primary_keyword,
        )
    )


    if explicit_place:

        return {
            "geo_policy":
                STRICT,

            "reason":
                (
                    "Specific named location "
                    "or geographic feature: "
                    + explicit_place
                ),

            "explicit_place":
                explicit_place,
        }


    # ----------------------------------------------
    # 2. COUNTRY ITSELF IS VISUAL SUBJECT
    # ----------------------------------------------

    if country_is_visual_subject(
        dialogue,
        project_country,
        analysis,
    ):

        return {
            "geo_policy":
                STRICT,

            "reason":
                (
                    "The project country itself "
                    "is part of the visual subject."
                ),

            "explicit_place":
                project_country,
        }


    # ----------------------------------------------
    # BUILD ANALYSIS TEXT
    # ----------------------------------------------

    combined_analysis = " ".join(
        [

            dialogue,

            clean_text(
                analysis.get(
                    "context",
                    ""
                )
            ),

            clean_text(
                analysis.get(
                    "subject",
                    ""
                )
            ),

            clean_text(
                analysis.get(
                    "action",
                    ""
                )
            ),

            clean_text(
                analysis.get(
                    "location",
                    ""
                )
            ),

            primary_keyword,
        ]
    )


    # ----------------------------------------------
    # 3. REGIONAL PROXY
    #
    # Geography matters visually,
    # but exact country is not mandatory.
    # ----------------------------------------------

    if contains_term(
        combined_analysis,
        BROAD_GEO_TERMS,
    ):

        return {
            "geo_policy":
                REGIONAL_PROXY,

            "reason":
                (
                    "Scene has geographic or "
                    "environmental character, "
                    "but no mandatory exact landmark."
                ),

            "explicit_place":
                None,
        }


    # ----------------------------------------------
    # 4. VISUAL PROXY
    #
    # Human activity / ordinary lifestyle /
    # object / generic activity.
    # ----------------------------------------------

    if contains_term(
        combined_analysis,
        VISUAL_PROXY_TERMS,
    ):

        return {
            "geo_policy":
                VISUAL_PROXY,

            "reason":
                (
                    "Main visual target is ordinary "
                    "human activity, lifestyle, "
                    "or a generic scene."
                ),

            "explicit_place":
                None,
        }


    # ----------------------------------------------
    # 5. GENERIC
    # ----------------------------------------------

    return {
        "geo_policy":
            GENERIC,

        "reason":
            (
                "No strong geographic requirement "
                "was detected."
            ),

        "explicit_place":
            None,
    }


# ==================================================
# REGIONAL PROFILE
# ==================================================

def get_regional_profile(
    country_key,
):

    return REGIONAL_PROFILES.get(
        normalized(
            country_key
        ),
        {
            "display":
                country_key,

            "regions":
                [],

            "proxy_countries":
                [],

            "visual_terms":
                [],
        },
    )


# ==================================================
# REMOVE HARD GEO WORDS FROM A QUERY
# ==================================================

def make_generic_query(
    query,
    project_country,
    profile,
):

    result = clean_text(
        query
    )


    remove_terms = []


    if project_country:

        remove_terms.append(
            project_country
        )


    remove_terms.extend(
        profile.get(
            "regions",
            []
        )
    )


    for term in remove_terms:

        if not term:

            continue


        result = re.sub(
            re.escape(
                term
            ),
            " ",
            result,
            flags=re.IGNORECASE,
        )


    result = re.sub(
        r"\s+",
        " ",
        result,
    ).strip()


    return result


# ==================================================
# BUILD SEARCH TIERS
# ==================================================

def build_search_tiers(
    scene,
    strategy,
):

    search = scene.get(
        "search",
        {},
    )


    project_context = scene.get(
        "project_context",
        {},
    )


    country = clean_text(
        project_context.get(
            "required_country",
            ""
        )
    )


    country_key = clean_text(
        project_context.get(
            "required_country_key",
            ""
        )
    )


    profile = get_regional_profile(
        country_key
    )


    primary = clean_text(
        search.get(
            "primary_keyword",
            ""
        )
    )


    keywords = [

        clean_text(
            item
        )

        for item in search.get(
            "keywords",
            []
        )

        if clean_text(
            item
        )
    ]


    generic_primary = (
        make_generic_query(
            primary,
            country,
            profile,
        )
        or primary
    )


    policy = strategy[
        "geo_policy"
    ]


    tiers = {

        "exact_geo": [],

        "regional_proxy": [],

        "visual_proxy": [],

        "generic": [],
    }


    # ==================================================
    # STRICT
    # ==================================================

    if policy == STRICT:

        tiers[
            "exact_geo"
        ].append(
            primary
        )


        for keyword in keywords[
            :3
        ]:

            tiers[
                "exact_geo"
            ].append(
                keyword
            )


        return tiers


    # ==================================================
    # REGIONAL PROXY
    # ==================================================

    if policy == REGIONAL_PROXY:

        if country:

            tiers[
                "exact_geo"
            ].append(
                f"{country} {generic_primary}"
            )


        for region in profile.get(
            "regions",
            []
        )[:
            3
        ]:

            tiers[
                "regional_proxy"
            ].append(
                f"{region} {generic_primary}"
            )


        for proxy_country in (
            profile.get(
                "proxy_countries",
                []
            )[:
                3
            ]
        ):

            tiers[
                "regional_proxy"
            ].append(
                f"{proxy_country} {generic_primary}"
            )


        for visual_term in (
            profile.get(
                "visual_terms",
                []
            )[:
                2
            ]
        ):

            tiers[
                "visual_proxy"
            ].append(
                f"{visual_term} {generic_primary}"
            )


        tiers[
            "generic"
        ].append(
            generic_primary
        )


        return tiers


    # ==================================================
    # VISUAL PROXY
    # ==================================================

    if policy == VISUAL_PROXY:

        for region in profile.get(
            "regions",
            []
        )[:
            2
        ]:

            tiers[
                "regional_proxy"
            ].append(
                f"{region} {generic_primary}"
            )


        for visual_term in (
            profile.get(
                "visual_terms",
                []
            )[:
                3
            ]
        ):

            tiers[
                "visual_proxy"
            ].append(
                f"{visual_term} {generic_primary}"
            )


        tiers[
            "generic"
        ].append(
            generic_primary
        )


        for keyword in keywords[
            :2
        ]:

            generic_keyword = (
                make_generic_query(
                    keyword,
                    country,
                    profile,
                )
            )


            if generic_keyword:

                tiers[
                    "generic"
                ].append(
                    generic_keyword
                )


        return tiers


    # ==================================================
    # GENERIC
    # ==================================================

    tiers[
        "generic"
    ].append(
        generic_primary
    )


    for keyword in keywords[
        :3
    ]:

        generic_keyword = (
            make_generic_query(
                keyword,
                country,
                profile,
            )
        )


        if generic_keyword:

            tiers[
                "generic"
            ].append(
                generic_keyword
            )


    return tiers


# ==================================================
# LOAD MANIFEST
# ==================================================

print("=" * 80)
print("58D-1A VISUAL STRATEGY OFFLINE TEST")
print("=" * 80)

print()
print(
    "Manifest:",
    MANIFEST,
)


if not MANIFEST.exists():

    raise FileNotFoundError(
        MANIFEST
    )


with open(
    MANIFEST,
    "r",
    encoding="utf-8",
) as file:

    manifest = json.load(
        file
    )


# ==================================================
# APPLY EXISTING PROJECT CONTEXT
#
# Read-only in memory.
# ==================================================

manifest = (
    enrich_manifest_with_project_context(
        manifest
    )
)


project_context = manifest.get(
    "project_context",
    {},
)


print()

print(
    "Project country:",
    project_context.get(
        "required_country"
    ),
)


print(
    "Country key:",
    project_context.get(
        "required_country_key"
    ),
)


# ==================================================
# CLASSIFY
# ==================================================

counts = Counter()

classified = []


for scene in manifest.get(
    "scenes",
    [],
):

    if scene.get(
        "scene_type",
        "speech",
    ) == "gap":

        continue


    strategy = classify_geo_policy(
        scene
    )


    policy = strategy[
        "geo_policy"
    ]


    counts[
        policy
    ] += 1


    tiers = build_search_tiers(
        scene,
        strategy,
    )


    classified.append(
        {
            "scene_id":
                scene.get(
                    "scene_id"
                ),

            "dialogue":
                scene.get(
                    "dialogue",
                    ""
                ),

            "policy":
                policy,

            "reason":
                strategy.get(
                    "reason"
                ),

            "explicit_place":
                strategy.get(
                    "explicit_place"
                ),

            "primary_keyword":
                scene.get(
                    "search",
                    {},
                ).get(
                    "primary_keyword",
                    ""
                ),

            "tiers":
                tiers,
        }
    )


# ==================================================
# DISPLAY RESULTS
# ==================================================

for item in classified:

    print()
    print("=" * 80)

    print(
        "SCENE:",
        item[
            "scene_id"
        ],
    )

    print("=" * 80)


    print(
        "Dialogue:",
        item[
            "dialogue"
        ],
    )


    print(
        "Old primary:",
        item[
            "primary_keyword"
        ],
    )


    print(
        "Geo policy:",
        item[
            "policy"
        ],
    )


    print(
        "Reason:",
        item[
            "reason"
        ],
    )


    if item[
        "explicit_place"
    ]:

        print(
            "Explicit place:",
            item[
                "explicit_place"
            ],
        )


    print()

    print(
        "SEARCH TIERS:"
    )


    for tier_name in [

        "exact_geo",

        "regional_proxy",

        "visual_proxy",

        "generic",

    ]:

        queries = item[
            "tiers"
        ][
            tier_name
        ]


        print()

        print(
            tier_name.upper()
            + ":"
        )


        if not queries:

            print(
                "  [NONE]"
            )

            continue


        for query in queries:

            print(
                "  -",
                query,
            )


# ==================================================
# SUMMARY
# ==================================================

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)


print(
    "STRICT:",
    counts[
        STRICT
    ],
)


print(
    "REGIONAL_PROXY:",
    counts[
        REGIONAL_PROXY
    ],
)


print(
    "VISUAL_PROXY:",
    counts[
        VISUAL_PROXY
    ],
)


print(
    "GENERIC:",
    counts[
        GENERIC
    ],
)


proxy_count = (

    counts[
        REGIONAL_PROXY
    ]

    +

    counts[
        VISUAL_PROXY
    ]

    +

    counts[
        GENERIC
    ]
)


print()

print(
    "Proxy-capable scenes:",
    proxy_count,
)


print(
    "Strict scenes:",
    counts[
        STRICT
    ],
)


# ==================================================
# BASIC TEST RESULT
# ==================================================

print()
print("=" * 80)


if (
    project_context.get(
        "required_country_key"
    )
    == "morocco"

    and

    proxy_count >= 5

    and

    counts[
        STRICT
    ] >= 1
):

    print(
        "VISUAL STRATEGY V1 OFFLINE TEST: PASS"
    )

else:

    print(
        "VISUAL STRATEGY V1 OFFLINE TEST: REVIEW REQUIRED"
    )


print("=" * 80)

print()

print(
    "No production file was modified."
)