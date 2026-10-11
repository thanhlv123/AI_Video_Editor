from pathlib import Path
from collections import Counter
import json
import re
import sys


# ==================================================
# PROJECT
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
# SOURCE MANIFEST
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

        "display":
            "Morocco",

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

        "display":
            "Serbia",

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

        "display":
            "Vietnam",

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
# NAMED PLACES
# ==================================================

KNOWN_PLACES = {

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
    "sahara",

    # Serbia
    "belgrade",
    "beograd",
    "novi sad",

    # Other landmarks
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
# HUMAN / DAILY-LIFE VISUALS
# ==================================================

HUMAN_ACTIVITY_TERMS = {

    "person",
    "people",

    "woman",
    "women",

    "man",
    "men",

    "young women",
    "young men",

    "family",
    "families",

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

    "smartphone",
    "phone",

    "social media",

    "university",

    "clothing",
    "fashion",

    "daily life",
    "lifestyle",

    "family gathering",
    "family customs",
}


# ==================================================
# ORDINARY VISUAL SUBJECTS
# ==================================================

GENERIC_VISUAL_TERMS = {

    "market",

    "vineyard",
    "grapevine",
    "grapevines",
    "grapes",

    "agriculture",
    "farming",
    "cultivation",

    "street",

    "house",
    "home",

    "apartment",

    "food",

    "coffee",

    "car",
    "traffic",
}


# ==================================================
# ENVIRONMENT TERMS
# ==================================================

ENVIRONMENT_TERMS = {

    "mountain",
    "mountains",

    "desert",

    "snow",
    "snowy",

    "ski",
    "skiing",

    "coast",
    "coastline",

    "sea",

    "river",

    "landscape",

    "village",

    "rural",

    "countryside",

    "forest",

    "valley",

    "ancient landscape",

    "ruins",
}


# ==================================================
# STRONG STRICT VISUAL CUES
# ==================================================

STRICT_GEO_CUES = {

    "map",
    "geographic",
    "geography",

    "border",

    "separated from",

    "aerial view",

    "country overview",

    "location map",
}


# ==================================================
# HELPERS
# ==================================================

def text(value):

    return str(
        value
        or ""
    ).strip()


def norm(value):

    return (
        text(value)
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )


def contains_any(
    source,
    terms,
):

    source = norm(
        source
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
            text(value),
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
# DETECT EXPLICIT PLACE IN CURRENT NARRATION ONLY
#
# IMPORTANT:
# We deliberately DO NOT inspect primary_keyword here.
#
# AI-generated keywords must not accidentally turn
# a proxy scene into a STRICT scene.
# ==================================================

def find_place_in_dialogue(
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
# IS COUNTRY ITSELF THE VISUAL SUBJECT?
# ==================================================

def country_is_visual_subject(
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

            norm(
                analysis.get(
                    "location"
                )
            ),
        ]
    )


    # ----------------------------------------------
    # Strong geographic description
    # ----------------------------------------------

    if contains_any(
        combined,
        STRICT_GEO_CUES,
    ):

        return True


    phrases = [

        "this is " + country_lower,

        country_lower
        + " an african country",

        country_lower
        + " is a country",

        "country separated from",

        "country coastline",

        "country geography",
    ]


    return any(
        phrase in combined
        for phrase in phrases
    )


# ==================================================
# IS THE NAMED PLACE THE VISUAL SUBJECT?
#
# Merely saying:
#
# "women in Casablanca"
#
# does NOT make Casablanca the visual subject.
#
# But:
#
# "snow on the Atlas Mountains"
#
# does.
# ==================================================

def place_is_visual_subject(
    place,
    dialogue,
    analysis,
):

    if not place:

        return False


    subject = norm(
        analysis.get(
            "subject"
        )
    )


    location = norm(
        analysis.get(
            "location"
        )
    )


    context = norm(
        analysis.get(
            "context"
        )
    )


    dialogue_lower = norm(
        dialogue
    )


    place_lower = norm(
        place
    )


    # ----------------------------------------------
    # HUMAN-ACTIVITY OVERRIDE
    #
    # Example:
    #
    # women in Casablanca wearing modern clothes
    #
    # Casablanca is context, not visual subject.
    # ----------------------------------------------

    human_visual = contains_any(
        subject
        + " "
        + context,
        HUMAN_ACTIVITY_TERMS,
    )


    if human_visual:

        return False


    # ----------------------------------------------
    # Famous / physical geographic feature
    # explicitly forms the visual subject.
    # ----------------------------------------------

    feature_words = {

        "mountains",
        "mountain",

        "strait",

        "tower",

        "canyon",

        "opera house",

        "desert",

        "river",

        "sea",

        "lake",
    }


    if contains_any(
        place_lower,
        feature_words,
    ):

        if (
            place_lower in subject
            or
            place_lower in context
            or
            place_lower in location
        ):

            return True


    # ----------------------------------------------
    # City/location with geographic visual cues
    # ----------------------------------------------

    geo_visual_cues = {

        "aerial",
        "skyline",
        "map",
        "coastline",
        "landmark",
        "cityscape",
        "geographic",
        "panorama",
    }


    combined = (
        subject
        + " "
        + context
        + " "
        + dialogue_lower
    )


    if (
        place_lower in combined
        and
        contains_any(
            combined,
            geo_visual_cues,
        )
    ):

        return True


    return False


# ==================================================
# CLASSIFIER
# ==================================================

def classify_scene(
    scene,
):

    dialogue = text(
        scene.get(
            "dialogue"
        )
    )


    analysis = scene.get(
        "analysis",
        {},
    )


    project_context = scene.get(
        "project_context",
        {},
    )


    country = text(
        project_context.get(
            "required_country"
        )
    )


    explicit_place = (
        find_place_in_dialogue(
            dialogue
        )
    )


    # ==================================================
    # 1. COUNTRY IS VISUAL SUBJECT
    # ==================================================

    if country_is_visual_subject(
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
        }


    # ==================================================
    # 2. NAMED PLACE IS ACTUAL VISUAL SUBJECT
    # ==================================================

    if place_is_visual_subject(
        explicit_place,
        dialogue,
        analysis,
    ):

        return {

            "geo_policy":
                STRICT,

            "reason":
                (
                    "Named geographic feature "
                    "is the visual subject: "
                    + str(
                        explicit_place
                    )
                ),

            "explicit_place":
                explicit_place,
        }


    # ==================================================
    # BUILD SEMANTIC DESCRIPTION
    # ==================================================

    combined = " ".join(
        [

            dialogue,

            text(
                analysis.get(
                    "context"
                )
            ),

            text(
                analysis.get(
                    "subject"
                )
            ),

            text(
                analysis.get(
                    "action"
                )
            ),

            text(
                analysis.get(
                    "location"
                )
            ),
        ]
    )


    # ==================================================
    # 3. HUMAN / DAILY LIFE
    #
    # Even if a city is mentioned,
    # we allow visual substitutes.
    # ==================================================

    if contains_any(
        combined,
        HUMAN_ACTIVITY_TERMS,
    ):

        return {

            "geo_policy":
                VISUAL_PROXY,

            "reason":
                (
                    "Human activity/lifestyle is "
                    "the primary visual subject; "
                    "location is contextual."
                ),

            "explicit_place":
                explicit_place,
        }


    # ==================================================
    # 4. ENVIRONMENT / LANDSCAPE
    #
    # Exact landmark was already caught above.
    #
    # Otherwise use regional visual similarity.
    # ==================================================

    if contains_any(
        combined,
        ENVIRONMENT_TERMS,
    ):

        return {

            "geo_policy":
                REGIONAL_PROXY,

            "reason":
                (
                    "Environment or landscape matters, "
                    "but exact geography is not mandatory."
                ),

            "explicit_place":
                explicit_place,
        }


    # ==================================================
    # 5. ORDINARY VISUAL SUBJECT
    # ==================================================

    if contains_any(
        combined,
        GENERIC_VISUAL_TERMS,
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
        }


    # ==================================================
    # 6. PLACE MENTION BUT NOT VISUAL SUBJECT
    # ==================================================

    if explicit_place:

        return {

            "geo_policy":
                REGIONAL_PROXY,

            "reason":
                (
                    "Named place is contextual rather "
                    "than the main visual subject."
                ),

            "explicit_place":
                explicit_place,
        }


    # ==================================================
    # 7. GENERIC
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
    }


# ==================================================
# REGIONAL PROFILE
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
# REMOVE GEO PREFIXES
# ==================================================

def genericize_query(
    query,
    scene,
):

    result = text(
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


    for item in sorted(
        remove_terms,
        key=lambda x: len(
            text(x)
        ),
        reverse=True,
    ):

        if not item:
            continue


        result = re.sub(
            re.escape(
                str(item)
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
# QUERY TIERS
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


    country = text(
        project_context.get(
            "required_country"
        )
    )


    profile = get_profile(
        scene
    )


    primary = text(
        search.get(
            "primary_keyword"
        )
    )


    keywords = [

        text(item)

        for item
        in search.get(
            "keywords",
            []
        )

        if text(item)
    ]


    generic_primary = (
        genericize_query(
            primary,
            scene,
        )
        or
        primary
    )


    policy = strategy[
        "geo_policy"
    ]


    explicit_place = text(
        strategy.get(
            "explicit_place"
        )
    )


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
                *keywords[:3],
            ]
        )


        return tiers


    # ==================================================
    # OPTIONAL EXACT QUERY
    #
    # Exact geography is preferred when available,
    # but NOT required for proxy scenes.
    # ==================================================

    if primary:

        tiers[
            "exact_geo"
        ].append(
            primary
        )


    # ==================================================
    # REGIONAL PROXY
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
    # DEDUPE
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
# EXPECTED MOROCCO RESULT
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
# LOAD
# ==================================================

print("=" * 80)
print("58D-1B VISUAL STRATEGY V2")
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


project = manifest.get(
    "project_context",
    {},
)


print()

print(
    "Project country:",
    project.get(
        "required_country"
    ),
)


print(
    "Country key:",
    project.get(
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


    if expected:

        expected_total += 1


        matched = (
            expected
            == policy
        )


        if matched:

            expected_pass += 1

    else:

        matched = True


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
        "Geo policy:",
        policy,
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


    if expected:

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
# FINAL
# ==================================================

print()
print("=" * 80)


if (

    project.get(
        "required_country_key"
    )
    == "morocco"

    and

    counts[
        STRICT
    ]
    == 2

    and

    proxy_count
    == 9

    and

    expected_pass
    == expected_total
):

    print(
        "VISUAL STRATEGY V2 OFFLINE TEST: PASS"
    )

else:

    print(
        "VISUAL STRATEGY V2 OFFLINE TEST: REVIEW REQUIRED"
    )


print("=" * 80)

print()

print(
    "No production file was modified."
)