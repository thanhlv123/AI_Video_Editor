from pathlib import Path
import py_compile
import shutil


ROOT = Path(__file__).resolve().parent.parent

FULL = ROOT / "pipeline" / "full_video_pipeline.py"
SCENE = ROOT / "pipeline" / "scene_pipeline.py"
MODULE = ROOT / "pipeline" / "context_geo.py"

BACKUP_FULL = (
    ROOT
    / "pipeline"
    / "full_video_pipeline_before_context_geo_v1.py"
)

BACKUP_SCENE = (
    ROOT
    / "pipeline"
    / "scene_pipeline_before_context_geo_v1.py"
)


print("=" * 70)
print("ENABLE CONTEXT + GEOGRAPHY GUARD V1")
print("=" * 70)


for path in (FULL, SCENE):

    if not path.exists():

        raise FileNotFoundError(
            path
        )


# ==================================================
# NEW MODULE
# ==================================================

module_code = r'''import re
from collections import Counter


# ==================================================
# COUNTRY ALIASES
#
# Deliberately conservative.
# A project country is only activated when it appears
# in at least two different speech scenes.
# ==================================================

COUNTRY_ALIASES = {

    "serbia": (
        "serbia",
        "serbian",
    ),

    "vietnam": (
        "vietnam",
        "viet nam",
        "vietnamese",
    ),

    "india": (
        "india",
        "indian",
    ),

    "south africa": (
        "south africa",
        "south african",
    ),

    "slovenia": (
        "slovenia",
        "slovenian",
    ),

    "singapore": (
        "singapore",
    ),

    "united arab emirates": (
        "united arab emirates",
        "uae",
    ),

    "netherlands": (
        "netherlands",
        "the netherlands",
        "dutch",
    ),

    "italy": (
        "italy",
        "italian",
    ),

    "belgium": (
        "belgium",
        "belgian",
    ),

    "hungary": (
        "hungary",
        "hungarian",
    ),

    "united kingdom": (
        "united kingdom",
        "great britain",
        "britain",
        "british",
    ),

    "south korea": (
        "south korea",
        "south korean",
    ),

    "france": (
        "france",
        "french",
    ),

    "germany": (
        "germany",
        "german",
    ),

    "spain": (
        "spain",
        "spanish",
    ),

    "portugal": (
        "portugal",
        "portuguese",
    ),

    "greece": (
        "greece",
        "greek",
    ),

    "croatia": (
        "croatia",
        "croatian",
    ),

    "bosnia and herzegovina": (
        "bosnia and herzegovina",
        "bosnia",
        "bosnian",
    ),

    "montenegro": (
        "montenegro",
        "montenegrin",
    ),

    "north macedonia": (
        "north macedonia",
        "macedonian",
    ),

    "romania": (
        "romania",
        "romanian",
    ),

    "bulgaria": (
        "bulgaria",
        "bulgarian",
    ),

    "austria": (
        "austria",
        "austrian",
    ),

    "switzerland": (
        "switzerland",
        "swiss",
    ),

    "czech republic": (
        "czech republic",
        "czechia",
        "czech",
    ),

    "slovakia": (
        "slovakia",
        "slovak",
    ),

    "poland": (
        "poland",
        "polish",
    ),

    "ukraine": (
        "ukraine",
        "ukrainian",
    ),

    "russia": (
        "russia",
        "russian",
    ),

    "united states": (
        "united states",
        "united states of america",
        "usa",
        "u.s.a",
    ),

    "canada": (
        "canada",
        "canadian",
    ),

    "mexico": (
        "mexico",
        "mexican",
    ),

    "brazil": (
        "brazil",
        "brazilian",
    ),

    "argentina": (
        "argentina",
        "argentinian",
    ),

    "australia": (
        "australia",
        "australian",
    ),

    "japan": (
        "japan",
        "japanese",
    ),

    "china": (
        "china",
        "chinese",
    ),

    "thailand": (
        "thailand",
        "thai",
    ),

    "indonesia": (
        "indonesia",
        "indonesian",
    ),

    "malaysia": (
        "malaysia",
        "malaysian",
    ),

    "philippines": (
        "philippines",
        "filipino",
    ),

    "cambodia": (
        "cambodia",
        "cambodian",
    ),

    "laos": (
        "laos",
        "laotian",
    ),

    "myanmar": (
        "myanmar",
        "burma",
        "burmese",
    ),

    "turkey": (
        "turkiye",
        "turkey",
        "turkish",
    ),

    "egypt": (
        "egypt",
        "egyptian",
    ),

    "morocco": (
        "morocco",
        "moroccan",
    ),

    "saudi arabia": (
        "saudi arabia",
        "saudi",
    ),

    "qatar": (
        "qatar",
        "qatari",
    ),
}


COUNTRY_DISPLAY = {

    key:
        " ".join(
            word.capitalize()
            for word in key.split()
        )

    for key
    in COUNTRY_ALIASES
}


COUNTRY_DISPLAY.update({

    "united states":
        "United States",

    "united kingdom":
        "United Kingdom",

    "united arab emirates":
        "United Arab Emirates",

    "south africa":
        "South Africa",

    "south korea":
        "South Korea",

    "north macedonia":
        "North Macedonia",

    "bosnia and herzegovina":
        "Bosnia and Herzegovina",

    "czech republic":
        "Czech Republic",
})


# ==================================================
# HIGH-CONFIDENCE CITY / PLACE HINTS
#
# Only explicit metadata is used.
# Unknown metadata is NOT rejected.
# ==================================================

PLACE_COUNTRY_HINTS = {

    "belgrade":
        "serbia",

    "beograd":
        "serbia",

    "novi sad":
        "serbia",

    "budapest":
        "hungary",

    "venice":
        "italy",

    "venetian":
        "italy",

    "oostende":
        "belgium",

    "ostend":
        "belgium",

    "the hague":
        "netherlands",

    "amsterdam":
        "netherlands",

    "bled":
        "slovenia",

    "dubai":
        "united arab emirates",

    "abu dhabi":
        "united arab emirates",

    "seoul":
        "south korea",

    "london":
        "united kingdom",

    "paris":
        "france",

    "berlin":
        "germany",

    "rome":
        "italy",

    "milan":
        "italy",

    "barcelona":
        "spain",

    "madrid":
        "spain",

    "lisbon":
        "portugal",

    "prague":
        "czech republic",

    "vienna":
        "austria",

    "zurich":
        "switzerland",

    "new york":
        "united states",

    "los angeles":
        "united states",

    "san francisco":
        "united states",

    "toronto":
        "canada",

    "sydney":
        "australia",

    "melbourne":
        "australia",

    "tokyo":
        "japan",

    "bangkok":
        "thailand",

    "hanoi":
        "vietnam",

    "ho chi minh":
        "vietnam",

    "saigon":
        "vietnam",

    "singapore":
        "singapore",

    "mumbai":
        "india",

    "delhi":
        "india",

    "cape town":
        "south africa",

    "johannesburg":
        "south africa",
}


# ==================================================
# NORMALIZE
# ==================================================

def _normalize(value):

    value = str(
        value
        or ""
    ).lower()

    value = value.replace(
        "_",
        " ",
    )

    value = value.replace(
        "-",
        " ",
    )

    value = value.replace(
        "/",
        " ",
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def _contains_phrase(
    text,
    phrase,
):

    text = _normalize(
        text
    )

    phrase = _normalize(
        phrase
    )

    if not phrase:
        return False

    pattern = (
        r"(?<![a-z0-9])"
        + re.escape(phrase)
        + r"(?![a-z0-9])"
    )

    return bool(
        re.search(
            pattern,
            text,
        )
    )


# ==================================================
# DETECT COUNTRY
# ==================================================

def detect_countries(
    text,
):

    text = _normalize(
        text
    )

    found = set()


    for country, aliases in (
        COUNTRY_ALIASES.items()
    ):

        for alias in aliases:

            if _contains_phrase(
                text,
                alias,
            ):

                found.add(
                    country
                )

                break


    for place, country in (
        PLACE_COUNTRY_HINTS.items()
    ):

        if _contains_phrase(
            text,
            place,
        ):

            found.add(
                country
            )


    return found


# ==================================================
# PROJECT COUNTRY
# ==================================================

def infer_project_country(
    scenes,
):

    counter = Counter()


    for scene in scenes:

        if (
            scene.get(
                "scene_type"
            )
            == "gap"
        ):
            continue


        analysis = scene.get(
            "analysis",
            {},
        )

        text = " ".join([

            str(
                scene.get(
                    "dialogue",
                    "",
                )
                or ""
            ),

            str(
                analysis.get(
                    "location",
                    "",
                )
                or ""
            ),

            str(
                analysis.get(
                    "context",
                    "",
                )
                or ""
            ),
        ])


        countries = detect_countries(
            text
        )


        # Count a country only once per scene.
        for country in countries:

            counter[
                country
            ] += 1


    if not counter:
        return None


    ordered = (
        counter.most_common()
    )

    best_country, best_count = (
        ordered[0]
    )


    # Conservative:
    # project geography must appear in >= 2 scenes.
    if best_count < 2:
        return None


    if len(ordered) > 1:

        second_count = (
            ordered[1][1]
        )

        # Ambiguous project.
        if (
            second_count
            == best_count
        ):
            return None


    return best_country


# ==================================================
# QUERY LOCATION CHECK
# ==================================================

def _already_mentions_country(
    text,
    country,
):

    detected = detect_countries(
        text
    )

    return country in detected


# ==================================================
# MANIFEST CONTEXT CARRYOVER
# ==================================================

def enrich_manifest_with_project_context(
    manifest,
):

    if not isinstance(
        manifest,
        dict,
    ):
        return manifest


    scenes = manifest.get(
        "scenes",
        [],
    )


    if not isinstance(
        scenes,
        list,
    ):
        return manifest


    required_country = (
        infer_project_country(
            scenes
        )
    )


    narration = " ".join(

        str(
            scene.get(
                "dialogue",
                "",
            )
            or ""
        ).strip()

        for scene in scenes

        if (
            scene.get(
                "dialogue"
            )
        )
    )


    # Keep context useful but bounded.
    narration = narration[
        :6000
    ]


    display_country = None


    if required_country:

        display_country = (
            COUNTRY_DISPLAY.get(
                required_country,
                required_country.title(),
            )
        )


    manifest[
        "project_context"
    ] = {

        "required_country":
            display_country,

        "required_country_key":
            required_country,

        "narration":
            narration,
    }


    for scene in scenes:

        scene[
            "project_context"
        ] = dict(
            manifest[
                "project_context"
            ]
        )


        if not required_country:
            continue


        if (
            scene.get(
                "scene_type"
            )
            == "gap"
        ):
            continue


        # ------------------------------------------
        # ANALYSIS CARRYOVER
        # ------------------------------------------

        analysis = scene.setdefault(
            "analysis",
            {},
        )


        original_location = str(
            analysis.get(
                "location",
                "",
            )
            or ""
        ).strip()


        analysis[
            "original_location"
        ] = original_location


        analysis[
            "project_country"
        ] = display_country


        if not _already_mentions_country(
            original_location,
            required_country,
        ):

            if original_location:

                analysis[
                    "location"
                ] = (
                    original_location
                    + "; project country: "
                    + display_country
                )

            else:

                analysis[
                    "location"
                ] = (
                    "Project country: "
                    + display_country
                )


        old_context = str(
            analysis.get(
                "context",
                "",
            )
            or ""
        ).strip()


        project_sentence = (
            "Project-wide geographic context: "
            + display_country
            + "."
        )


        if (
            display_country.lower()
            not in old_context.lower()
        ):

            analysis[
                "context"
            ] = (
                old_context
                + " "
                + project_sentence
            ).strip()


        # ------------------------------------------
        # SEARCH QUERY CARRYOVER
        # ------------------------------------------

        search = scene.setdefault(
            "search",
            {},
        )


        original_primary = str(
            search.get(
                "primary_keyword",
                "",
            )
            or ""
        ).strip()


        original_keywords = (
            search.get(
                "keywords",
                [],
            )
        )


        if not isinstance(
            original_keywords,
            list,
        ):

            original_keywords = []


        original_keywords = [

            str(item).strip()

            for item
            in original_keywords

            if str(item).strip()
        ]


        if (
            original_primary
            and
            not _already_mentions_country(
                original_primary,
                required_country,
            )
        ):

            targeted_primary = (
                display_country
                + " "
                + original_primary
            )

        else:

            targeted_primary = (
                original_primary
            )


        targeted_keywords = []


        for keyword in (
            original_keywords[:3]
        ):

            if _already_mentions_country(
                keyword,
                required_country,
            ):

                targeted_keywords.append(
                    keyword
                )

            else:

                targeted_keywords.append(
                    display_country
                    + " "
                    + keyword
                )


        combined = []


        for keyword in (
            targeted_keywords
            + original_keywords
        ):

            key = (
                keyword.lower()
            )

            if (
                keyword
                and
                key not in [
                    x.lower()
                    for x in combined
                ]
            ):

                combined.append(
                    keyword
                )


        search[
            "original_primary_keyword"
        ] = original_primary


        search[
            "primary_keyword"
        ] = targeted_primary


        # Keep query count controlled.
        search[
            "keywords"
        ] = combined[:6]


        scene[
            "context_carryover"
        ] = True


    return manifest


# ==================================================
# CANDIDATE GEOGRAPHY GUARD
# ==================================================

def filter_geography_candidates(
    scene,
    candidates,
):

    candidates = list(
        candidates
        or []
    )


    project_context = scene.get(
        "project_context",
        {},
    )


    required_country = (
        project_context.get(
            "required_country_key"
        )
    )


    if not required_country:

        return (
            candidates,
            [],
            False,
        )


    kept = []

    rejected = []


    for candidate in candidates:

        metadata_text = " ".join([

            str(
                candidate.get(
                    "title",
                    "",
                )
                or ""
            ),

            str(
                candidate.get(
                    "source_url",
                    "",
                )
                or ""
            ),

            str(
                candidate.get(
                    "photographer",
                    "",
                )
                or ""
            ),
        ])


        detected = detect_countries(
            metadata_text
        )


        if (
            detected
            and
            required_country
            not in detected
        ):

            rejected.append({

                "provider":
                    candidate.get(
                        "provider"
                    ),

                "media_id":
                    candidate.get(
                        "media_id"
                    ),

                "detected_countries":
                    sorted(
                        detected
                    ),

                "title":
                    candidate.get(
                        "title",
                        "",
                    ),
            })

            continue


        kept.append(
            candidate
        )


    # Safety:
    # never destroy an entire candidate pool.
    # The visual AI still receives project location
    # and can judge the remaining conflict.
    bypassed = False


    if (
        candidates
        and
        not kept
    ):

        kept = candidates

        bypassed = True


    return (
        kept,
        rejected,
        bypassed,
    )
'''


# ==================================================
# VERIFY NEW MODULE IN MEMORY
# ==================================================

compile(
    module_code,
    str(MODULE),
    "exec",
)

print(
    "context_geo.py in-memory compile: PASS"
)


# ==================================================
# BACKUPS
# ==================================================

if not BACKUP_FULL.exists():

    shutil.copy2(
        FULL,
        BACKUP_FULL,
    )

    print(
        "Backup:",
        BACKUP_FULL,
    )


if not BACKUP_SCENE.exists():

    shutil.copy2(
        SCENE,
        BACKUP_SCENE,
    )

    print(
        "Backup:",
        BACKUP_SCENE,
    )


module_existed = (
    MODULE.exists()
)

module_backup = (
    ROOT
    / "pipeline"
    / "context_geo_before_v1.py"
)


if (
    module_existed
    and
    not module_backup.exists()
):

    shutil.copy2(
        MODULE,
        module_backup,
    )


# ==================================================
# PATCH FULL VIDEO PIPELINE
# ==================================================

full_text = FULL.read_text(
    encoding="utf-8"
)


if (
    "CONTEXT CARRYOVER 58B V1"
    not in full_text
):

    class_marker = (
        "class FullVideoPipelineError"
    )


    class_pos = full_text.find(
        class_marker
    )


    if class_pos < 0:

        raise RuntimeError(
            "Could not locate "
            "FullVideoPipelineError."
        )


    import_text = (
        "from pipeline.context_geo import "
        "enrich_manifest_with_project_context\n\n"
    )


    if (
        "from pipeline.context_geo import "
        not in full_text
    ):

        full_text = (
            full_text[:class_pos]
            + import_text
            + full_text[class_pos:]
        )


    full_lines = (
        full_text.splitlines()
    )


    ai_start = None


    for index, line in enumerate(
        full_lines
    ):

        if (
            line.strip()
            == "ai_manifest = ("
        ):

            nearby = "\n".join(
                full_lines[
                    index:
                    index + 12
                ]
            )

            if "_run_ai_stage(" in nearby:

                ai_start = index


    if ai_start is None:

        raise RuntimeError(
            "Could not locate outer "
            "ai_manifest = _run_ai_stage block."
        )


    balance = 0
    seen = False
    ai_end = None


    for index in range(
        ai_start,
        len(full_lines),
    ):

        for char in (
            full_lines[index]
        ):

            if char == "(":

                balance += 1
                seen = True

            elif char == ")":

                balance -= 1


        if (
            seen
            and
            balance == 0
        ):

            ai_end = index
            break


    if ai_end is None:

        raise RuntimeError(
            "Could not determine end of "
            "AI manifest assignment."
        )


    indent = (
        full_lines[ai_start]
        [
            :
            len(
                full_lines[ai_start]
            )
            - len(
                full_lines[
                    ai_start
                ].lstrip()
            )
        ]
    )


    carryover_block = [

        "",

        indent
        + "# CONTEXT CARRYOVER 58B V1",

        indent
        + "ai_manifest = (",

        indent
        + "    enrich_manifest_with_project_context(",

        indent
        + "        ai_manifest",

        indent
        + "    )",

        indent
        + ")",

        "",

        indent
        + "project_country = (",

        indent
        + "    ai_manifest.get(",

        indent
        + '        "project_context",',

        indent
        + "        {},",

        indent
        + "    ).get(",

        indent
        + '        "required_country"',

        indent
        + "    )",

        indent
        + ")",

        "",

        indent
        + "print(",

        indent
        + '    "Project geography:",',

        indent
        + "    project_country",

        indent
        + '    or "not established",',

        indent
        + ")",
    ]


    insert_at = (
        ai_end + 1
    )


    full_lines[
        insert_at:
        insert_at
    ] = carryover_block


    full_text = (
        "\n".join(
            full_lines
        )
        + "\n"
    )


# ==================================================
# PATCH SCENE PIPELINE
# ==================================================

scene_text = SCENE.read_text(
    encoding="utf-8"
)


if (
    "GEOGRAPHY GUARD 58B V1"
    not in scene_text
):

    class_marker = (
        "class ScenePipeline:"
    )


    class_pos = scene_text.find(
        class_marker
    )


    if class_pos < 0:

        raise RuntimeError(
            "Could not locate "
            "class ScenePipeline."
        )


    import_text = (
        "from pipeline.context_geo import (\n"
        "    filter_geography_candidates,\n"
        ")\n\n"
    )


    if (
        "filter_geography_candidates"
        not in scene_text[
            :class_pos
        ]
    ):

        scene_text = (
            scene_text[:class_pos]
            + import_text
            + scene_text[class_pos:]
        )


    scene_lines = (
        scene_text.splitlines()
    )


    search_call = None


    for index, line in enumerate(
        scene_lines
    ):

        if (
            "self.search_manager.search_scene("
            in line
        ):

            search_call = index


    if search_call is None:

        raise RuntimeError(
            "Could not locate "
            "search_manager.search_scene()."
        )


    assignment_start = None


    for index in range(
        search_call,
        max(
            -1,
            search_call - 10,
        ),
        -1,
    ):

        if (
            scene_lines[index]
            .strip()
            .startswith(
                "candidates ="
            )
        ):

            assignment_start = index
            break


    if assignment_start is None:

        raise RuntimeError(
            "Could not locate candidates assignment."
        )


    balance = 0
    seen = False
    assignment_end = None


    for index in range(
        assignment_start,
        len(scene_lines),
    ):

        for char in (
            scene_lines[index]
        ):

            if char == "(":

                balance += 1
                seen = True

            elif char == ")":

                balance -= 1


        if (
            seen
            and
            balance == 0
        ):

            assignment_end = index
            break


    if assignment_end is None:

        raise RuntimeError(
            "Could not determine end of "
            "candidate search assignment."
        )


    indent = (
        scene_lines[
            assignment_start
        ]
        [
            :
            len(
                scene_lines[
                    assignment_start
                ]
            )
            - len(
                scene_lines[
                    assignment_start
                ].lstrip()
            )
        ]
    )


    geo_block = [

        "",

        indent
        + "# GEOGRAPHY GUARD 58B V1",

        indent
        + "(",

        indent
        + "    candidates,",

        indent
        + "    geography_rejected,",

        indent
        + "    geography_bypassed,",

        indent
        + ") = filter_geography_candidates(",

        indent
        + "    scene,",

        indent
        + "    candidates,",

        indent
        + ")",

        "",

        indent
        + "if geography_rejected:",

        "",

        indent
        + "    stock.setdefault(",

        indent
        + '        "geography_rejected",',

        indent
        + "        [],",

        indent
        + "    ).extend(",

        indent
        + "        geography_rejected",

        indent
        + "    )",

        "",

        indent
        + "    print(",

        indent
        + '        "Geography guard rejected:",',

        indent
        + "        len(geography_rejected),",

        indent
        + "    )",

        "",

        indent
        + "    for rejected in (",

        indent
        + "        geography_rejected[:5]",

        indent
        + "    ):",

        "",

        indent
        + "        print(",

        indent
        + '            "  -",',

        indent
        + '            rejected.get("provider"),',

        indent
        + '            rejected.get("media_id"),',

        indent
        + '            rejected.get("detected_countries"),',

        indent
        + "        )",

        "",

        indent
        + "if geography_bypassed:",

        "",

        indent
        + "    print(",

        indent
        + '        "Geography guard safety bypass: "',

        indent
        + '        "all candidates conflicted."',

        indent
        + "    )",
    ]


    insert_at = (
        assignment_end + 1
    )


    scene_lines[
        insert_at:
        insert_at
    ] = geo_block


    scene_text = (
        "\n".join(
            scene_lines
        )
        + "\n"
    )


# ==================================================
# SAFETY CHECKS BEFORE WRITE
# ==================================================

required_full = [

    "CONTEXT CARRYOVER 58B V1",

    "enrich_manifest_with_project_context",

    "Project geography:",
]


for marker in required_full:

    if marker not in full_text:

        raise RuntimeError(
            "Missing FullVideoPipeline marker: "
            + marker
        )


required_scene = [

    "GEOGRAPHY GUARD 58B V1",

    "filter_geography_candidates",

    "Geography guard rejected:",
]


for marker in required_scene:

    if marker not in scene_text:

        raise RuntimeError(
            "Missing ScenePipeline marker: "
            + marker
        )


# Compile modified source entirely in memory.

compile(
    full_text,
    str(FULL),
    "exec",
)

compile(
    scene_text,
    str(SCENE),
    "exec",
)

print(
    "Modified source in-memory compile: PASS"
)


# ==================================================
# WRITE
# ==================================================

try:

    MODULE.write_text(
        module_code,
        encoding="utf-8",
    )

    FULL.write_text(
        full_text,
        encoding="utf-8",
    )

    SCENE.write_text(
        scene_text,
        encoding="utf-8",
    )


    py_compile.compile(
        str(MODULE),
        doraise=True,
    )

    py_compile.compile(
        str(FULL),
        doraise=True,
    )

    py_compile.compile(
        str(SCENE),
        doraise=True,
    )


except Exception:

    print()
    print(
        "WRITE/COMPILE FAILED - RESTORING"
    )


    shutil.copy2(
        BACKUP_FULL,
        FULL,
    )

    shutil.copy2(
        BACKUP_SCENE,
        SCENE,
    )


    if module_existed:

        if module_backup.exists():

            shutil.copy2(
                module_backup,
                MODULE,
            )

    else:

        if MODULE.exists():

            MODULE.unlink()


    raise


# ==================================================
# SUCCESS
# ==================================================

print()
print("=" * 70)
print("CONTEXT + GEOGRAPHY GUARD V1: PASS")
print("=" * 70)

print(
    "Context carryover -> PASS"
)

print(
    "Project country inference -> PASS"
)

print(
    "Stock geography pre-filter -> PASS"
)

print(
    "V5 fallback was not modified"
)

print(
    "Local/visual weights were not modified"
)