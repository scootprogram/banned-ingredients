-- Banned-ingredients database (SQLite).
-- Designed to grow to millions of rows: every lookup column is indexed and
-- nothing is ever hard-deleted (bans are deactivated and the change is logged).
--
-- A product is described by up to three text fields, and each ban says which
-- of them it applies to:
--   ingredients  what's in it (food, cosmetics, cleaners)
--   packaging    what it comes in
--   material     what it's made of (durable goods: utensils, clothing, ...)

PRAGMA foreign_keys = ON;

-- One row per thing you want to avoid.
CREATE TABLE IF NOT EXISTS banned_ingredients (
    id               INTEGER PRIMARY KEY,
    slug             TEXT NOT NULL UNIQUE,          -- short stable key, e.g. 'soy'
    name             TEXT NOT NULL,                 -- display name
    applies_to       TEXT NOT NULL DEFAULT 'ingredients',  -- comma list of ingredients,packaging,material
    include_children INTEGER NOT NULL DEFAULT 1,    -- 1 = also ban every taxonomy descendant
    category         TEXT,                          -- allergen, additive, oil, material, ...
    reason           TEXT,                          -- why it's banned
    strictness       TEXT NOT NULL DEFAULT 'exact'  -- 'exact' or 'traces' (also exclude "may contain")
                     CHECK (strictness IN ('exact', 'traces')),
    active           INTEGER NOT NULL DEFAULT 1,    -- 0 = removed (soft delete)
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Taxonomy nodes a ban covers. kind 'ingredient' is matched against ingredient
-- text; kind 'packaging' against packaging and material text.
CREATE TABLE IF NOT EXISTS ban_roots (
    ingredient_id INTEGER NOT NULL REFERENCES banned_ingredients (id),
    kind          TEXT NOT NULL CHECK (kind IN ('ingredient', 'packaging')),
    node_id       TEXT NOT NULL,                    -- e.g. 'en:soya-bean', 'en:plastic'
    PRIMARY KEY (ingredient_id, kind, node_id)
);
CREATE INDEX IF NOT EXISTS idx_roots_node ON ban_roots (kind, node_id);

-- Extra names that should map to a ban. Matched as whole words, so the alias
-- 'soy' catches 'soy lecithin' but 'wheat' does not catch 'buckwheat'.
-- `fields` narrows an alias to some of the ban's fields (NULL = all of them),
-- e.g. the plastic code 'PET' only counts in packaging/material text.
CREATE TABLE IF NOT EXISTS aliases (
    id            INTEGER PRIMARY KEY,
    ingredient_id INTEGER NOT NULL REFERENCES banned_ingredients (id),
    alias         TEXT NOT NULL,
    alias_norm    TEXT NOT NULL,                    -- normalized form used for matching
    fields        TEXT,                             -- NULL or comma list, e.g. 'packaging,material'
    match         TEXT NOT NULL DEFAULT 'word'      -- 'word' = whole words; 'stem' = anywhere inside a word
                  CHECK (match IN ('word', 'stem')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (ingredient_id, alias_norm)
);
CREATE INDEX IF NOT EXISTS idx_aliases_norm ON aliases (alias_norm);

-- Phrases that must NOT trigger a ban even though they contain an alias,
-- e.g. 'coconut milk' for the milk ban.
CREATE TABLE IF NOT EXISTS exceptions (
    id            INTEGER PRIMARY KEY,
    ingredient_id INTEGER NOT NULL REFERENCES banned_ingredients (id),
    phrase        TEXT NOT NULL,
    phrase_norm   TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (ingredient_id, phrase_norm)
);

-- Every add / remove / restore / edit, forever.
CREATE TABLE IF NOT EXISTS change_log (
    id            INTEGER PRIMARY KEY,
    at            TEXT NOT NULL DEFAULT (datetime('now')),
    ingredient_id INTEGER REFERENCES banned_ingredients (id),
    action        TEXT NOT NULL,                    -- add, edit, remove, restore, alias_add, root_add, ...
    details       TEXT,                             -- JSON of what changed
    note          TEXT
);
CREATE INDEX IF NOT EXISTS idx_log_ingredient ON change_log (ingredient_id);

-- Open Food Facts taxonomies (reloadable with `load-taxonomy`):
--   kind 'ingredient' = ingredients.txt + additives.txt
--   kind 'packaging'  = packaging_materials.txt
CREATE TABLE IF NOT EXISTS taxonomy_nodes (
    kind TEXT NOT NULL,
    id   TEXT NOT NULL,                             -- e.g. 'en:soya-lecithin'
    name TEXT NOT NULL,                             -- first listed name
    PRIMARY KEY (kind, id)
);
CREATE TABLE IF NOT EXISTS taxonomy_synonyms (
    kind      TEXT NOT NULL,
    node_id   TEXT NOT NULL,
    lang      TEXT NOT NULL,
    text_norm TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_syn_text ON taxonomy_synonyms (kind, text_norm);
CREATE TABLE IF NOT EXISTS taxonomy_parents (
    kind      TEXT NOT NULL,
    child_id  TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    PRIMARY KEY (kind, child_id, parent_id)
);
CREATE INDEX IF NOT EXISTS idx_parent ON taxonomy_parents (kind, parent_id);
