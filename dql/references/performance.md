# DQL Query Performance

> Version bound: see `SKILL.md`.

**Most of the rules below are enforced by the build.** `./bin/dqlcheckheck` prints a `warning:` line, on
stderr, for every shape it can decide from the query alone — the codes are listed in `SKILL.md` under
*Warnings*. This file is what you read to understand a warning, and what you work through for the part
the build cannot see: anything that depends on the data model (field names, field types, array-typed
fields) or on what the user actually asked for.

Every query falls into one of two shapes:

- **Cheap**: the query reads only the rows it needs. The time range, the conditions, the grouping, the
  ordering and the paging are applied as the data is read, and only the result travels back.
- **Expensive**: the query reads the whole time range and filters afterwards. The answer is still
  correct, but the cost scales with the raw data the condition was supposed to remove — this is the
  usual cause of slow queries and memory pressure.

The query text alone does not tell you which shape you got; the shape of the clauses does. Each rule
below gives the form to prefer and what the other form costs.

## Rules

1. **Set an explicit time range.** A query without one is rejected —
   `bind error: bind DQL select: time window is required`. A range far wider than the question is the
   single largest cost in any query; narrow it to what the question needs.
2. **Keep every condition in the column-vs-constant shape.** `{host = 'web-01'}` reads only the
   matching rows. Comparing two columns cannot be applied as the data is read, so the query reads the
   whole time range and compares afterwards. DQL text always treats the right-hand side of a
   comparison as a literal, so this shape appears only when you hand-write JSON — a `wheres` entry
   whose right side is `{"type":"IdentExpr","value":"total"}` builds, but reads everything. Keep the
   right side a literal.
3. **Write multiple values with `IN`, never `=` against an array.** `{host = ['a','b']}` can return an
   empty result with no error — see *Silent failures*. Use `{host IN ['a','b']}`.
4. **Do not fold a cheap condition into an `OR` with an expensive one.** A condition is applied as a
   whole: if one part of it cannot be applied while the data is read, none of it is. So
   `{host = 'web-01' OR message =~ 'timeout.*'}` reads the whole time range, even though
   `host = 'web-01'` on its own would not. When the two conditions were meant as `AND`, write them as
   separate top-level conditions — `{host = 'web-01', message =~ 'timeout.*'}` — and the cheap one
   still applies. When you genuinely need the `OR`, accept the cost.
5. **Prefer aggregates that are cheap everywhere.** The `Cheap everywhere` list below is the safe set;
   the `Cost depends on the workspace` table names the ones that are only cheap on some.
6. **Do not write arithmetic across aggregates.** `sum(a) / count(b)` reads the whole time range on
   some workspaces, because the whole aggregation then runs after the read instead of as the data is
   read. Return the two aggregates and divide afterwards, or accept the cost.
7. **Group by bare column names.** Grouping by an expression (`concat(service, env)`,
   `regexp_extract_all(...)`) is cheap only on some workspaces; a bare column is cheap everywhere.
8. **Group by low-cardinality dimensions, never by a per-record identifier.** The number of groups is
   the number of distinct values in the grouping field, so a high-cardinality field makes the result
   as large as the input:

   - Grouping by `trace_id`, `request_id`, `session_id`, `span_id` or `message` gives roughly **one
     group per record** — the `GROUP BY` stops summarising anything, and every group still has to be
     built, ordered and returned.
   - The problem is the group count, not the field being "wrong": `service`, `status`, `host`, `env`
     and `cluster_id` are dimensions, and those are exactly what you want to group by.

   **You cannot read the cardinality off the query, so check it.** Before grouping on a field you are
   unsure about, ask for the count with `show_tag_value_cardinality(keyin=['field'])` or
   `show_series_cardinality()` (see `references/metadata-discovery.md`). If that number is in the same
   range as the row count, you are grouping by an identifier rather than a dimension.

   The build warns on names that look unique per record (`group_by_high_cardinality`), but it cannot
   see the data: treat the warning as a prompt to check, and its absence as no information at all.
9. **Name the source when you know it.** A wildcard source (`L::*:(*)`) reads every source in the
   index, so it is the broadest read available — the right choice when the name is genuinely unknown,
   and worth replacing once you learn the name. The rest of the query still bounds the cost, so pair it
   with a time range, a condition on a dimension, and `LIMIT`/`SLIMIT`. On a metric query the wildcard
   covers the measurement only; the field still has to be named.
10. **`HAVING` filters the result, not the input.** It is evaluated after grouping, so it never reduces
   how much data is read. A condition that can be written in `wheres` belongs there — `{status = 500}`
   reads less than `HAVING status = 500`. Keep `HAVING` for conditions on aggregate values
   (`HAVING avg_usage > 80`), where there is no cheaper form.
11. **Bound what comes back.** `LIMIT` / `OFFSET` page rows **inside** a group — the points of a
    series. `SLIMIT` / `SOFFSET` page **groups**. They bound different things, so a grouped query
    usually needs both: `SLIMIT` caps how many groups come back, `LIMIT` caps how many points per
    group. Use `100` unless the user names a number, say which bound you chose, and remember that a
    metric query gets no cost reduction from either — they are still the only thing limiting the
    response.
12. **Order by time, and paginate with a cursor.**
    - **Do not order by a non-time column** (`order_by_non_time`): results are ordered by time when
      you do not ask for anything else, so an explicit `ORDER BY time DESC` is optional. What is not
      optional is avoiding `ORDER BY <non_time_field>` (such as `ORDER BY latency DESC`): it forces
      every candidate record across the whole time window into an in-memory heap to be sorted,
      creating large CPU and memory spikes over wide ranges. If you genuinely need that order, narrow
      the time window and the filters first. `ORDER BY` on a dynamic variant/JSON string is rejected
      outright, and `ORDER BY` on an array field is unsupported.
    - **Prefer cursor-based pagination over deep `OFFSET`** (`deep_offset_paging`): `LIMIT 100 OFFSET 10000` scans and
      discards 10,000 rows. For continuous list pagination, use cursor pagination (seek method) by
      passing the timestamp of the last row from the previous page into the `WHERE` clause:
      ```dql
      // Page 1
      L::nginx:(*) [1h] ORDER BY time DESC LIMIT 100

      // Page 2 (cursor: feed time from the 100th record of Page 1)
      L::nginx:(*) { time < 1727000000000000000 } [1h] ORDER BY time DESC LIMIT 100
      ```
      This performs an O(1) index seek rather than scanning and discarding thousands of rows.
13. **Subqueries and `SHIFT` are additional reads.** A subquery is a separate query: its own
    conditions decide its own cost, and a condition in the outer query does not reduce what the inner
    query reads. `SHIFT` runs the query twice — the current window and the shifted one — so it
    roughly doubles the cost. Keep both as cheap as possible.
14. **Filter on clustered dimensions whenever possible.**
    Data blocks are physically clustered by primary routing keys. Common default clustered
    dimensions include:
    - **Logs (`L`) & Traces (`T`)**: `service`, `status`, `time`
    - **Network (`N`)**: `source`, `host`, `time`
    - **Events (`E`)**: `df_source`, `df_status`, `time`
    Filtering on these clustered fields (e.g. `{service = 'api', status >= 500}`) allows the query
    to prune entire data blocks without reading their records. Always prefer filtering on these
    dimensions over filtering solely on non-clustered free-text fields.

## Cheap everywhere

Cheap for log queries on scalar fields; the notes after the table list the exceptions, and
*Metrics versus logs* overrides it for `M::`.

| Category | Use |
| --- | --- |
| Comparisons | string `=` / `!=`; `IN` / `NOT IN` (strings and numbers); numeric `>` `>=` `<` `<=`; `= nil` / `!= nil` |
| Regex and matching | `=~` / `!~`; `re(col, p)`; `search(col, kw)`; `match(col, kw)`; `cidr(col, cidr)`; `wildcard(col, p)` |
| Wrapping a column in a function | only `int` `float` `string` `md5` `lower` `upper` `trim` `ltrim` `rtrim` `length` `regexp_replace` |
| Aggregates | `avg` `min` `max` `sum` `count` `first` `last` `any` `distinct` `distinct_by_collapse` `count_distinct` `field_values` `percentile` `median` `histogram_auto` |
| Grouping | bare column names |
| Ordering and paging | `ORDER BY` on a column or alias; `LIMIT`; `SLIMIT` |

1. **On metrics, nothing in the aggregate row is cheap**, and neither are the numeric comparisons in
   the first row. See *Metrics versus logs*.
2. **Array fields are the exception to the comparison and matching rows.** `>` `<` `>=` `<=` and
   `search` / regex on an array field read the whole time range and filter afterwards; `=`, `!=` and
   `IN` do not. Prefer `IN` / `NOT IN` on array fields — the `=` / `!=` forms are historical
   compatibility syntax with contains semantics, and they are easy to misread.
3. **`distinct`, `distinct_by_collapse` and `field_values` return every value of the field**, so their
   result grows with the number of distinct values. `collect_distinct(x, n)` caps the list at `n` and
   `count_distinct(x)` returns only a count — prefer one of those when the field may be
   high-cardinality and you do not need the values themselves.
   (`collect_distinct` is listed in the table below as the more expensive of the two on some
   workspaces — pick it for the bounded result, not for the cost.)

**Always expensive, on every workspace**: `CASE … END` as a condition; comparing two columns; `>`
`<` `>=` `<=` on an array field; `search` / regex on an array field; `>` `<` `>=` `<=` against
`nil`; `HAVING`; `ORDER BY` on a non-time column over wide ranges; `ORDER BY` on dynamic variant/JSON
string columns (not physical columns); `last()` combined with TopN group ranking (forces full sample).

## Metrics versus logs

Metric queries (`M::`) are the constrained case:

- **Only string conditions reduce the read.** `{host = 'web-01'}` narrows the data;
  `{usage > 80}` does not — it is applied after everything is read, so it is correct but leaves the
  query just as expensive. Always pair a numeric threshold with a strong string condition:
  `{host = 'web-01', usage > 80}`.
- **Grouping, ordering and paging reduce nothing either.** The cost of a metric query is decided
  entirely by how much its string conditions narrow the data.
- **Wildcard fields are rejected**: `M::cpu:(count(*)) [1h]` fails with
  `bind error: metric queries do not support wildcard fields; specify metric field names explicitly`.
  Name the field — `M::cpu:(count(usage_user)) [1h]`.
- The useful conditions are the string dimensions: `host`, `service`, `env`, and similar.

Log queries (`L::`, `O::`, `T::`, `R::`) accept `*`, and their conditions, grouping, ordering and
paging are applied as the data is read.

## Cost depends on the workspace

The forms below are correct everywhere but cheap only on some workspaces. If you do not know which
workspace you are querying, treat the right column as expensive and prefer the left.

| Prefer | Instead of |
| --- | --- |
| `max(x)` | `mode(x)` |
| `distinct(x)` | `collect_distinct(x)` |
| `increase(x)` for Counter metrics, or two queries compared | `difference(x)` |
| `sum(x)` / `count(x)`, divided afterwards | `rate_over_sum(x)` / `rate_over_count(x)` |
| a `wheres` condition | `count_filter(x, [v…])` (and `count(CASE …)` is no cheaper) |
| grouping by a bare column | `concat` / `regexp_extract_all` in `GROUP BY` |
| the bare aggregate | `round` / `abs` / `ceil` / `floor` wrapped around `avg` |

## Silent failures

The rules above are about cost — breaking them is slow but correct. The two below are different: they
produce **wrong or empty results with no error**, so nothing catches them and the output looks
plausible.

| Form | What silently happens | Safe form |
| --- | --- | --- |
| `{host = ['a','b']}` on a scalar field | On some workspaces the condition is dropped and never applied, so you get an empty result | `{host IN ['a','b']}` |
| `{field = 'value'}` on a tokenized log field | Matches **by token**, not by whole value, so it can return rows whose value is not equal to the literal | Confirm the field is matched by whole value, or filter on a different field |

## Warning Reference

`dqlcheck` reports non-fatal cost and semantics warnings on stderr (`"warnings"` array in JSON mode):

| Warning Code | Meaning & Guidance |
| --- | --- |
| `eq_array` | `=` / `!=` against array literal silently returns empty on some backends; use `IN` / `NOT IN` |
| `column_vs_column` | Comparison between two columns scans full range; compare column vs literal constant |
| `aggregate_arithmetic` | Arithmetic across aggregates (e.g. `sum(a)/count(b)`); runs in compute layer |
| `having_on_column` | `HAVING` on a bare non-aggregate column; move it to `wheres` |
| `case_in_condition` | `CASE` expression used inside `WHERE` condition |
| `wrapped_field_condition` | Function wrapped around field in filter outside the pushdown set |
| `expensive_aggregate` | Aggregate function that forces whole time range scan |
| `group_by_expression` | Grouping on expression instead of bare column |
| `group_by_high_cardinality` | Grouping dimension looks like unique ID (trace_id, message); check cardinality |
| `metric_numeric_only_filter` | Metric filter has only numeric thresholds without tag conditions to prune read |
| `or_loses_cheap_side` | `OR` condition where one side is expensive, defeating pushdown of both |
| `unbounded_result` | Missing `LIMIT` on detail query or `SLIMIT` on grouped query |
| `shift_double_read` | `SHIFT` reads both target and base windows |
| `subquery_extra_read` | Subquery executes as an extra read |
| `order_by_non_time` | `ORDER BY` on non-time column forces memory sort; prefer time ordering |
| `deep_offset_paging` | Large `OFFSET` scans and discards rows; use cursor pagination (`time < last_time`) |
| `step_exceeds_window` | CRITICAL: aggregation `step` > window duration; produces zero points |
| `explosive_point_count` | CRITICAL: window generates > 10,000 points per series; risks driver OOM |
| `inverted_time_window` | CRITICAL: `from` duration is smaller than `to` duration (time window backward) |
| `non_positive_limit` | CRITICAL: `LIMIT` or `SLIMIT` is <= 0 |
| `string_nil_comparison` | CRITICAL: comparing with literal string `"nil"` rather than `= nil` |
| `leading_wildcard` | Leading wildcard pattern in regex or search prevents index filtering |
| `match_with_regex_syntax` | `match()` contains regex syntax; `match()` is strictly literal substring |
| `regex_for_literal` | Regex without metacharacters matches single value; use `=` or `IN` |
| `regex_for_alternation` | Regex `a\|b\|c` over literals; use `IN ['a', 'b', 'c']` |

## Checklist before delivering

Every warning the build printed is either fixed or explained in the delivery notes. The items below
are the ones it cannot decide, so they are still yours:

- [ ] Time range present **and** the one the question needs, rather than merely present?
- [ ] Field names and types confirmed with the user, not guessed?
- [ ] Any condition on an **array-typed** field checked against the array rules above?
- [ ] No silent-failure shape the build cannot see (the tokenized-field row)?
- [ ] No `*` in a metric query?
