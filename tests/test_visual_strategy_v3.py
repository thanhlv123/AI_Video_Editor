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
# POLICIES
# ==================================================

STRICT = "STRICT"
REGIONAL_PROXY = "REGIONAL_PROXY"
VISUAL_PROXY = "VISUAL_PROXY"
GENERIC = "GENERIC"


# ==================================================
# REGIONAL VISUAL PROFILES
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
}


# ==================================================
# KNOWN PLACES
#
# IMPORTANT:
# A place mention alone does NOT mean STRICT.
# ==================================================

KNOWN_PLACES = {

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
    "sahara",

    "belgrade",
    "beograd",
    "novi sad",

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
# STRONG REGIONAL SUBJECT TERMS
#
# If these appear in PRIMARY KEYWORD or SUBJECT,
# the visual itself is mainly environment/geography.
# ==================================================

STRONG_REGIONAL_SUBJECT_TERMS = {

    "mountain community",
    "mountain village",
    "mountain landscape",

    "snowy mountain",
    "snow covered mountain",

    "ski resort",
    "skiing",

    "ancient landscape",
    "desert landscape",
    "mountain landscape",
    "coastal landscape",

    "north africa",
    "north african landscape",

    "ancestral homeland",
    "homeland landscape",

    "rural settlement",
    "mountain settlement",

    "desert",
    "mountains",
    "mountain",

    "coastline",
    "coastal",

    "valley",
    "forest",
    "ruins",
}


# ==================================================
# HUMAN VISUAL SUBJECT TERMS
#
# Deliberately DO NOT include generic:
#
# people
# ancestors
# armies
#
# because those caused V2 false positives.
# ==================================================

HUMAN_VISUAL_TERMS = {

    "young woman",
    "young women",

    "woman",
    "women",

    "young man",
    "young men",

    "student",
    "students",

    "university student",

    "family",
    "families",

    "multigenerational family",

    "farmer",
    "farmers",

    "worker",
    "workers",

    "street fashion",

    "modern clothing",
    "clothing",
    "fashion",

    "smartphone",
    "using phone",
    "social media",

    "family gathering",

    "wedding gathering",

    "daily life",
    "urban lifestyle",
}


# ==================================================
# ORDINARY VISUAL SUBJECT TERMS
#
# These scenes do NOT require the real country.
# ==================================================

VISUAL_OBJECT_TERMS = {

    "bride market",
    "market",

    "vineyard",
    "vineyards",

    "grapevine",
    "grapevines",

    "grape cultivation",
    "vineyard cultivation",

    "cultivation",
    "cultivated field",

    "grape harvest",

    "agriculture",
    "farming",

    "food",
    "coffee",

    "traffic",

    "street",

    "house",
    "home",
    "apartment",
}


# ==================================================
# STRICT GEOGRAPHY CUES
# ==================================================

STRICT_GEO_CUES = {

    "map",
    "geographic",
    "geography",

    "country overview",

    "border",

    "separated from",

    "strait",

    "aerial coastline",

    "location map",
}


# ==================================================
# PHYSICAL NAMED FEATURES
#
# If clearly the visual subject -> STRICT.
# ==================================================

PHYSICAL_FEATURES = {

    "atlas mountains",
    "strait of gibraltar",

    "eiffel tower",
    "burj khalifa",
    "mount fuji",
    "grand canyon",
    "big ben",
    "colosseum",
    "sydney opera house",
}


# ==================================================
# HELPERS
# ==================================================

def clean(value):

    return str(
        value
        or ""
    ).strip()


def norm(value):

    return (
        clean(value)
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )


def contains_any(
    value,
    terms,
):

    source = norm(
        value
    )

    return any(
        norm(term) in source
        for term in terms
    )


def dedupe(
    values,
):

    result = []

    seen = set()


    for value in values:

        value = re.sub(
            r"\s+",
            " ",
            clean(value),
        ).strip()


        if not value:
            continue


        key = value.lower()


        if key in seen:
            continue


        seen.add(
            key
        )

        result.append(
            value
        )


    return result


# ==================================================
# FIND PLACE IN ORIGINAL DIALOGUE
#
# Never use AI-generated keyword for this.
# ==================================================

def find_dialogue_place(
    dialogue,
):

    dialogue_lower = norm(
        dialogue
    )


    for place in sorted(
        KNOWN_PLACES,
        key=len,
        reverse=True,
    ):

        if place in dialogue_lower:

            return place


    return None


# ==================================================
# COUNTRY IS MAIN VISUAL SUBJECT
# ==================================================

def country_is_main_subject(
    dialogue,
    analysis,
    country,
):

    if not country:
        return False


    dialogue_lower = norm(
        dialogue
    )


    country_lower = norm(
        country
    )


    if country_lower not in dialogue_lower:
        return False


    combined = " ".join(
        [

            dialogue_lower,

            norm(
                analysis.get(
                    "subject"
                )
            ),

            norm(
                analysis.get(
                    "context"
                )
            ),
        ]
    )


    if contains_any(
        combined,
        STRICT_GEO_CUES,
    ):

        return True


    if (
        "this is "
        + country_lower
    ) in dialogue_lower:

        return True


    return False


# ==================================================
# NAMED PLACE IS MAIN VISUAL SUBJECT
# ==================================================

def named_place_is_main_subject(
    place,
    dialogue,
    analysis,
    primary_keyword,
):

    if not place:
        return False


    place_lower = norm(
        place
    )


    subject = norm(
        analysis.get(
            "subject"
        )
    )


    context = norm(
        analysis.get(
            "context"
        )
    )


    primary = norm(
        primary_keyword
    )


    dialogue_lower = norm(
        dialogue
    )


    # ==================================================
    # HUMAN VISUAL OVERRIDE
    #
    # "young women in Casablanca"
    #
    # Location is only context.
    # ==================================================

    if contains_any(
        subject
        + " "
        + primary,
        HUMAN_VISUAL_TERMS,
    ):

        return False


    # ==================================================
    # PHYSICAL FEATURE
    #
    # Atlas Mountains etc.
    # ==================================================

    if place_lower in PHYSICAL_FEATURES:

        if (
            place_lower in dialogue_lower
            and
            (
                place_lower in subject
                or
                place_lower in primary
                or
                place_lower in context
            )
        ):

            return True


    # ==================================================
    # CITY / LOCATION AS LANDSCAPE SUBJECT
    # ==================================================

    landscape_cues = {

        "skyline",
        "cityscape",
        "aerial",
        "panorama",
        "coastline",
        "landmark",
        "map",
    }


    if (
        place_lower in subject
        or
        place_lower in primary
    ):

        if contains_any(
            subject
            + " "
            + primary,
            landscape_cues,
        ):

            return True


    return False


# ==================================================
# CLASSIFY
# ==================================================

def classify_scene(
    scene,
):

    dialogue = clean(
        scene.get(
            "dialogue"
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


    country = clean(
        project_context.get(
            "required_country"
        )
    )


    primary_keyword = clean(
        search.get(
            "primary_keyword"
        )
    )


    subject = clean(
        analysis.get(
            "subject"
        )
    )


    action = clean(
        analysis.get(
            "action"
        )
    )


    context = clean(
        analysis.get(
            "context"
        )
    )


    location = clean(
        analysis.get(
            "location"
        )
    )


    explicit_place = (
        find_dialogue_place(
            dialogue
        )
    )


    # ==================================================
    # PRIORITY 1
    # COUNTRY ITSELF
    # ==================================================

    if country_is_main_subject(
        dialogue,
        analysis,
        country,
    ):

        return {
            "geo_policy":
                STRICT,

            "reason":
                (
                    "Project country itself is "
                    "the geographic visual subject."
                ),

            "explicit_place":
                country,

            "signal":
                "country_subject",
        }


    # ==================================================
    # PRIORITY 2
    # REAL NAMED LANDMARK / FEATURE
    # ==================================================

    if named_place_is_main_subject(
        explicit_place,
        dialogue,
        analysis,
        primary_keyword,
    ):

        return {
            "geo_policy":
                STRICT,

            "reason":
                (
                    "Specific named geographic feature "
                    "is the main visual subject."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "named_feature",
        }


    # ==================================================
    # PRIMARY VISUAL SIGNAL
    #
    # Use SUBJECT + PRIMARY KEYWORD first.
    #
    # This is the key V3 improvement.
    # ==================================================

    primary_visual = " ".join(
        [
            subject,
            primary_keyword,
        ]
    )


    # ==================================================
    # PRIORITY 3
    # STRONG ENVIRONMENT / REGION SUBJECT
    #
    # Examples:
    #
    # mountain community
    # ski resort
    # ancient North Africa landscape
    # ==================================================

    if contains_any(
        primary_visual,
        STRONG_REGIONAL_SUBJECT_TERMS,
    ):

        # ----------------------------------------------
        # Vineyard exception:
        #
        # vineyard/grapes are ordinary stock subjects.
        # They should remain VISUAL_PROXY.
        # ----------------------------------------------

        if contains_any(
            primary_visual,
            {
                "vineyard",
                "grapevine",
                "grapevines",
                "grape cultivation",
            },
        ):

            return {
                "geo_policy":
                    VISUAL_PROXY,

                "reason":
                    (
                        "Vineyard/agricultural subject "
                        "can use visually compatible "
                        "proxy footage."
                    ),

                "explicit_place":
                    explicit_place,

                "signal":
                    "visual_object",
            }


        return {
            "geo_policy":
                REGIONAL_PROXY,

            "reason":
                (
                    "Primary visual subject is "
                    "environmental/geographic, but "
                    "exact country is not mandatory."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "regional_subject",
        }


    # ==================================================
    # PRIORITY 4
    # HUMAN / LIFESTYLE SUBJECT
    # ==================================================

    if contains_any(
        primary_visual,
        HUMAN_VISUAL_TERMS,
    ):

        return {
            "geo_policy":
                VISUAL_PROXY,

            "reason":
                (
                    "Primary visual subject is human "
                    "activity/lifestyle; location is "
                    "contextual."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "human_subject",
        }


    # ==================================================
    # PRIORITY 5
    # ORDINARY OBJECT / ACTIVITY
    # ==================================================

    if contains_any(
        primary_visual,
        VISUAL_OBJECT_TERMS,
    ):

        return {
            "geo_policy":
                VISUAL_PROXY,

            "reason":
                (
                    "Ordinary visual subject can use "
                    "visually compatible proxy footage."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "visual_object",
        }


    # ==================================================
    # SECONDARY SIGNAL
    #
    # Only now consult action/context/location/dialogue.
    # ==================================================

    secondary = " ".join(
        [
            action,
            context,
            location,
            dialogue,
        ]
    )


    # ==================================================
    # PRIORITY 6
    # ENVIRONMENT IN SECONDARY CONTEXT
    # ==================================================

    if contains_any(
        secondary,
        STRONG_REGIONAL_SUBJECT_TERMS,
    ):

        return {
            "geo_policy":
                REGIONAL_PROXY,

            "reason":
                (
                    "Scene carries a strong regional "
                    "or environmental visual character."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "secondary_region",
        }


    # ==================================================
    # PRIORITY 7
    # HUMAN SECONDARY
    # ==================================================

    if contains_any(
        secondary,
        HUMAN_VISUAL_TERMS,
    ):

        return {
            "geo_policy":
                VISUAL_PROXY,

            "reason":
                (
                    "Human/lifestyle imagery is the "
                    "best available visual proxy."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "secondary_human",
        }


    # ==================================================
    # PRIORITY 8
    # ORDINARY VISUAL SECONDARY
    # ==================================================

    if contains_any(
        secondary,
        VISUAL_OBJECT_TERMS,
    ):

        return {
            "geo_policy":
                VISUAL_PROXY,

            "reason":
                (
                    "Ordinary visual subject can use "
                    "proxy footage."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "secondary_object",
        }


    # ==================================================
    # PRIORITY 9
    # PLACE MENTION ONLY
    # ==================================================

    if explicit_place:

        return {
            "geo_policy":
                REGIONAL_PROXY,

            "reason":
                (
                    "Named place is contextual rather "
                    "than a mandatory visible landmark."
                ),

            "explicit_place":
                explicit_place,

            "signal":
                "contextual_place",
        }


    # ==================================================
    # GENERIC
    # ==================================================

    return {
        "geo_policy":
            GENERIC,

        "reason":
            (
                "No mandatory geographic or regional "
                "visual requirement."
            ),

        "explicit_place":
            None,

        "signal":
            "generic",
    }


# ==================================================
# PROFILE
# ==================================================

def get_profile(
    scene,
):

    project_context = scene.get(
        "project_context",
        {},
    )


    country_key = norm(
        project_context.get(
            "required_country_key"
        )
    )


    return REGIONAL_PROFILES.get(
        country_key,
        {
            "display":
                project_context.get(
                    "required_country",
                    ""
                ),

            "regions":
                [],

            "proxy_countries":
                [],

            "visual_terms":
                [],
        },
    )


# ==================================================
# REMOVE COUNTRY/REGION FROM QUERY
# ==================================================

def genericize_query(
    query,
    scene,
):

    result = clean(
        query
    )


    project_context = scene.get(
        "project_context",
        {},
    )


    profile = get_profile(
        scene
    )


    remove_terms = [

        project_context.get(
            "required_country",
            ""
        ),

        *profile.get(
            "regions",
            []
        ),
    ]


    for term in sorted(
        remove_terms,
        key=lambda x: len(
            clean(x)
        ),
        reverse=True,
    ):

        if not term:
            continue


        result = re.sub(
            re.escape(
                str(term)
            ),
            " ",
            result,
            flags=re.IGNORECASE,
        )


    return re.sub(
        r"\s+",
        " ",
        result,
    ).strip()


# ==================================================
# BUILD SEARCH TIERS
# ==================================================

def build_query_tiers(
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


    country = clean(
        project_context.get(
            "required_country"
        )
    )


    profile = get_profile(
        scene
    )


    primary = clean(
        search.get(
            "primary_keyword"
        )
    )


    keywords = [

        clean(item)

        for item
        in search.get(
            "keywords",
            []
        )

        if clean(item)
    ]


    generic_primary = (
        genericize_query(
            primary,
            scene,
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
        ] = dedupe(
            [
                primary,
                *keywords[:4],
            ]
        )


        return tiers


    # ==================================================
    # PROXY SCENES
    #
    # Keep exact query as ONE optional source,
    # not as a hard requirement.
    # ==================================================

    if primary:

        tiers[
            "exact_geo"
        ].append(
            primary
        )


    # ==================================================
    # REGIONAL
    # ==================================================

    if policy == REGIONAL_PROXY:

        for region in (
            profile.get(
                "regions",
                []
            )[:3]
        ):

            tiers[
                "regional_proxy"
            ].append(
                f"{region} {generic_primary}"
            )


        for proxy_country in (
            profile.get(
                "proxy_countries",
                []
            )[:3]
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
            )[:3]
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


    # ==================================================
    # VISUAL PROXY
    # ==================================================

    elif policy == VISUAL_PROXY:

        for region in (
            profile.get(
                "regions",
                []
            )[:2]
        ):

            tiers[
                "regional_proxy"
            ].append(
                f"{region} {generic_primary}"
            )


        for visual_term in (
            profile.get(
                "visual_terms",
                []
            )[:3]
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


        for keyword in keywords[:3]:

            generic_keyword = (
                genericize_query(
                    keyword,
                    scene,
                )
            )


            if generic_keyword:

                tiers[
                    "generic"
                ].append(
                    generic_keyword
                )


    # ==================================================
    # GENERIC
    # ==================================================

    else:

        tiers[
            "generic"
        ].append(
            generic_primary
        )


        for keyword in keywords[:4]:

            generic_keyword = (
                genericize_query(
                    keyword,
                    scene,
                )
            )


            if generic_keyword:

                tiers[
                    "generic"
                ].append(
                    generic_keyword
                )


    # ==================================================
    # DEDUPE ALL
    # ==================================================

    for tier_name in tiers:

        tiers[
            tier_name
        ] = dedupe(
            tiers[
                tier_name
            ]
        )


    return tiers


# ==================================================
# EXPECTED MOROCCO CLASSIFICATION
# ==================================================

EXPECTED = {

    "scene_001":
        VISUAL_PROXY,

    "scene_002":
        STRICT,

    "scene_003":
        VISUAL_PROXY,

    "scene_004":
        VISUAL_PROXY,

    "scene_005":
        STRICT,

    "scene_006":
        REGIONAL_PROXY,

    "scene_007":
        VISUAL_PROXY,

    "scene_008":
        REGIONAL_PROXY,

    "scene_009":
        VISUAL_PROXY,

    "scene_010":
        REGIONAL_PROXY,

    "scene_011":
        REGIONAL_PROXY,
}


# ==================================================
# LOAD MANIFEST
# ==================================================

print("=" * 80)
print("58D-1C VISUAL STRATEGY V3")
print("=" * 80)


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

expected_pass = 0

expected_total = 0


for scene in manifest.get(
    "scenes",
    [],
):

    if scene.get(
        "scene_type",
        "speech",
    ) == "gap":

        continue


    scene_id = scene.get(
        "scene_id"
    )


    strategy = classify_scene(
        scene
    )


    policy = strategy[
        "geo_policy"
    ]


    tiers = build_query_tiers(
        scene,
        strategy,
    )


    counts[
        policy
    ] += 1


    expected = EXPECTED.get(
        scene_id
    )


    matched = (
        expected
        == policy
    )


    if expected:

        expected_total += 1


        if matched:

            expected_pass += 1


    print()
    print("=" * 80)

    print(
        "SCENE:",
        scene_id,
    )

    print("=" * 80)


    print(
        "Dialogue:",
        scene.get(
            "dialogue",
            ""
        ),
    )


    print(
        "Subject:",
        scene.get(
            "analysis",
            {},
        ).get(
            "subject",
            ""
        ),
    )


    print(
        "Primary:",
        scene.get(
            "search",
            {},
        ).get(
            "primary_keyword",
            ""
        ),
    )


    print(
        "Geo policy:",
        policy,
    )


    print(
        "Signal:",
        strategy.get(
            "signal"
        ),
    )


    print(
        "Reason:",
        strategy.get(
            "reason"
        ),
    )


    print(
        "Explicit place:",
        strategy.get(
            "explicit_place"
        ),
    )


    print(
        "Expected:",
        expected,
    )


    print(
        "Policy check:",
        (
            "PASS"
            if matched
            else "FAIL"
        ),
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

        print()

        print(
            tier_name.upper()
            + ":"
        )


        queries = tiers[
            tier_name
        ]


        if not queries:

            print(
                "  [NONE]"
            )


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


print(
    "Expected policy checks:",
    f"{expected_pass}/{expected_total}",
)


# ==================================================
# FINAL RESULT
# ==================================================

print()
print("=" * 80)


if (

    project_context.get(
        "required_country_key"
    )
    == "morocco"

    and

    counts[
        STRICT
    ]
    == 2

    and

    counts[
        REGIONAL_PROXY
    ]
    == 4

    and

    counts[
        VISUAL_PROXY
    ]
    == 5

    and

    proxy_count
    == 9

    and

    expected_pass
    == expected_total
):

    print(
        "VISUAL STRATEGY V3 OFFLINE TEST: PASS"
    )

else:

    print(
        "VISUAL STRATEGY V3 OFFLINE TEST: REVIEW REQUIRED"
    )


print("=" * 80)

print()

print(
    "No production file was modified."
)