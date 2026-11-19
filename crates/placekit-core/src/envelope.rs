//! The tolerant envelope scanner: reading the fields of a
//! Google error envelope from a body the strict whole
//! document parse refused, or never attempted. The scanner
//! is a subsystem of its own, with its own invariants (the
//! head scan, the preflight depth walk, the detail caps),
//! and it moved out of the error module so the Error type
//! system that consumes its readings and the scanner that
//! produces them each read on their own (audit A50-064).

/// Message for an error response whose body is not a Google envelope.
/// The body is not quoted (R18-A6). Error text is the surface callers
/// log most, and an unparsed body is wholly server chosen, so quoting
/// it would let a hostile or compromised endpoint place arbitrary
/// text into caller logs and echo request data back through the same
/// channel. The body size is the fact the message carries, or the
/// read cap when the read stopped there and the size is unknown; the
/// HTTP status is not repeated here because every variant's headline
/// already carries it (Round 25, Minor 1). A parsed envelope is a
/// different case and keeps its own message and attributes: those
/// are the API's structured diagnostic, not raw body text. The
/// status is accepted so every error construction path takes the
/// same inputs. It does not shape the message.
pub(crate) fn non_envelope_message(_status: u16, body: &str, read_cap: Option<usize>) -> String {
    if body.trim().is_empty() {
        return "no error body".to_owned();
    }
    match read_cap {
        // The read stopped at the cap, so the prefix length is not
        // the body size and the message must not present it as one
        // (Round 23): the true size is unknown once reading stops.
        // The message opens with the fact rather than the HTTP
        // status (Round 25, Minor 1): every variant's headline
        // already carries the status, so a status here printed it
        // twice in one rendering.
        Some(cap) => format!(
            "error body read stopped at the {cap} byte cap, so the full size is unknown, not a Places error envelope"
        ),
        None => format!(
            "error body of {} bytes, not a Places error envelope",
            body.len()
        ),
    }
}

/// One usable field set read from a Google error envelope. The parse
/// is field by field on purpose (R4-09): each field is taken when it is
/// present and rightly typed and skipped when it is not, so one
/// mistyped field cannot discard the status, message and details the
/// rest of the envelope carried.
pub(crate) struct EnvelopeParts {
    pub(crate) status: Option<String>,
    pub(crate) message: Option<String>,
    pub(crate) code: Option<i64>,
    pub(crate) details: Vec<serde_json::Value>,
    /// True when these parts came from the tolerant head scan
    /// and the scan stopped before the error object closed, so
    /// a field read as absent may only be unread. Always false
    /// for the whole document parse, whose absent fields are
    /// genuinely absent.
    pub(crate) partial: bool,
}

/// The character bound on server supplied text carried into an
/// exception. The envelope status and message are truncated to
/// it when the error is built, and every string inside the
/// parsed details is truncated to it in the parse funnel (Round
/// 25, Minor 6; the status joined them in Round 28, Finding 1,
/// after the audit found it passing through whole while every
/// neighbouring field was capped). The caps are defined to be
/// one bound, so they read from this one constant rather than
/// from literals that only imply the coupling (Round 25 landing
/// repair).
pub(crate) const ENVELOPE_TEXT_CAP_CHARS: usize = 500;

/// Read the envelope fields of a response body, or `None` when the
/// body carries no `error` object at all.
///
/// A body whose bracket nesting reaches the parser recursion
/// limit anywhere is known before the parse starts to be a body
/// the parse cannot accept, so past the preflight size bound it
/// goes to the tolerant scan directly (Round 29, Finding 1). The
/// skipped attempt was not free: when a parse fails inside
/// nested containers, every open frame on the unwind path
/// rebuilds its error position by scanning the input from the
/// start, so the attempt priced at roughly the open frame count
/// times the bytes before the failure point, seconds on a multi
/// megabyte body. The scan reads the same head either way, so the
/// outcome is unchanged. At or below the bound the parse
/// keeps its own word, so ordinary bodies pay no walk at all.
/// The worst unwind at the bound itself is not small change:
/// a tripping body of exactly the bound size measured between
/// 402 and 970 milliseconds across three runs on the develop
/// (debug) build under load (Round 31, Info I2), against 92
/// to 136 milliseconds for the same shapes one byte past the
/// bound, where the walk replaces the attempt. The release
/// build constant remains unmeasured from this box.
/// Past the bound the walk itself runs only when the body's
/// bracket census reaches the limit (see [`preflight_trip`]): a
/// large body of few brackets, a long string or a flat list,
/// cannot nest to the limit, so its parse runs exactly as it did
/// before the preflight existed and pays no walk either.
///
/// Past that carve out, the whole document parse is tried first and
/// its field by field posture is unchanged (R4-09). When the whole
/// parse refuses the body, the envelope head fields are recovered
/// tolerantly instead
/// (Round 25, Major 1 and the red team depth finding): the parse is
/// all or nothing, so a body truncated by the error read cap, or
/// carrying a value nested past the parser depth limit anywhere
/// inside it, lost the status and message and code its head carried
/// complete, and classification fell back to the bare HTTP code. The
/// tolerant scan reads only the head, so neither body size nor
/// nesting anywhere in the body can defeat it. The scan recovers
/// the details array entry by entry (Round 41, Finding 4): an
/// entry the strict parse refuses degrades alone and clean
/// siblings survive, a poisoned string elsewhere in the body
/// costs the array nothing, and the whole array degrades to
/// empty only when its own container is unreadable in the text,
/// a cut off array being the standing shape.
///
/// String values inside parsed details are capped at the same 500
/// character discipline as the envelope message (Round 25, Minor
/// 6). The message cap alone left the details beside it bounded
/// only by the body cap, and on a success status envelope that cap
/// is the 32 MiB success cap rather than the error read cap, so a
/// hostile or broken endpoint could park a details payload of that
/// size inside an exception callers routinely log or retain.
pub(crate) fn parse_envelope(body: &str) -> Option<EnvelopeParts> {
    if preflight_trip(body).is_some() {
        return parse_envelope_head(body);
    }
    let value: serde_json::Value = match serde_json::from_str(body) {
        Ok(value) => value,
        Err(_) => return parse_envelope_head(body),
    };
    let error = value.get("error")?.as_object()?;
    let mut details = error
        .get("details")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    for detail in &mut details {
        cap_detail_strings(detail);
    }
    Some(EnvelopeParts {
        status: error
            .get("status")
            .and_then(|v| v.as_str())
            .map(str::to_owned),
        message: error
            .get("message")
            .and_then(|v| v.as_str())
            .map(str::to_owned),
        code: error.get("code").and_then(serde_json::Value::as_i64),
        details,
        partial: false,
    })
}

/// Recover the entries of one details array from its raw text,
/// entry by entry (Round 41, Finding 4). The text is the complete
/// array span the head scan delimited, closing bracket included.
/// Each entry is sliced out by the scan's own value skip and
/// parsed on its own, so an entry the strict parse refuses costs
/// that entry alone, and the entries that parse are kept in wire
/// order, each under the same string cap the whole parse route
/// applies. An entry whose own nesting passes the parser limit
/// fails its parse the same way, alone.
fn details_from_array_text(array: &[u8]) -> Vec<serde_json::Value> {
    let Ok(text) = std::str::from_utf8(array) else {
        return Vec::new();
    };
    let mut scan = HeadScan::new(text);
    scan.skip_ws();
    if !scan.eat(b'[') {
        return Vec::new();
    }
    let mut entries = Vec::new();
    loop {
        scan.skip_ws();
        if scan.at_end() || scan.eat(b']') {
            break;
        }
        let start = scan.pos;
        if !scan.skip_value() {
            break;
        }
        if let Ok(mut entry) = serde_json::from_str::<serde_json::Value>(&text[start..scan.pos]) {
            cap_detail_strings(&mut entry);
            entries.push(entry);
        }
        scan.skip_ws();
        if !scan.eat(b',') {
            break;
        }
    }
    entries
}

/// Truncate every string value inside one parsed detail at
/// [`ENVELOPE_TEXT_CAP_CHARS`] characters, the envelope message
/// discipline. The walk is
/// iterative, over the values of objects and the items of arrays;
/// object keys are names rather than values and keep their length.
fn cap_detail_strings(value: &mut serde_json::Value) {
    let mut stack: Vec<&mut serde_json::Value> = vec![value];
    while let Some(node) = stack.pop() {
        match node {
            serde_json::Value::String(text) => {
                if text.chars().count() > ENVELOPE_TEXT_CAP_CHARS {
                    *text = text.chars().take(ENVELOPE_TEXT_CAP_CHARS).collect();
                }
            }
            serde_json::Value::Array(items) => stack.extend(items.iter_mut()),
            serde_json::Value::Object(map) => stack.extend(map.values_mut()),
            _ => {}
        }
    }
}

/// Recover the envelope head fields from a body the whole document
/// parse refused. The scan walks the top level object to the
/// `error` key, then reads that object's scalar fields, skipping
/// every other value with an iterative depth walk that no nesting
/// can exhaust. A field whose value is not complete in the text is
/// read as absent, matching the field by field posture of the
/// whole parse, and a failure further into the error object never
/// discards head fields already read: the head is the
/// classification.
///
/// Duplicate keys resolve last wins, as the whole document parse
/// resolves them (Round 25 landing repair). The walk does not
/// stop at the first `error` key: a later error object replaces
/// an earlier one, and a later `error` value that is not an
/// object clears an earlier one (Round 31, Decoder Minor F1),
/// because the whole parse reads the last `error` value and a
/// non object value there is no envelope at all. An `error`
/// value that is not an object and stands before any envelope
/// is skipped like any other value rather than ending the scan.
/// One limit stands where the data runs out: a later error
/// object cut off before it yields a head field or a complete
/// details array does not erase an earlier complete one,
/// because the first readable value is the only data there is,
/// and a later non object value cut off
/// before it is fully read does not clear one either, for the
/// same reason. A scan that recovers no head field
/// at all and no details reports no envelope, the same verdict
/// the whole parse gives an error object with no usable field,
/// so the caller takes the bare HTTP fallback and its wording.
/// A recovered nonempty details array makes an envelope on its
/// own (A50-009): an error object carrying details and no head
/// field is still the server's error report, and the details
/// are the diagnostic the envelope exists to carry. The
/// recorded empty-object wording divergence stands apart from
/// this rule, because an empty object carries no details
/// either, so it still reports no envelope exactly as it did
/// before.
///
/// When the walk finds nothing and did not complete, one
/// recovery pass runs ([`HeadScan::recover_envelope`]): a
/// sibling container that never closes by the depth count
/// swallows the error key into its own skip, and the walk
/// above never sees it as a key at all (Round 31, Decoder
/// Minor F3). A walk that walked the whole object and found
/// nothing is authoritative, and no pass runs behind it: its
/// verdicts include the last wins clearing a later non object
/// value performs, and a recovery that re-read the body
/// behind the walk would resurrect what the walk cleared.
/// The clearing is authoritative on its own as well. A walk
/// that cleared an envelope and was then cut short carries
/// the cleared fact beside its result, distinct from having
/// found nothing, and no pass runs behind a clearing either,
/// so a cut clearing answers exactly as its completed twin
/// does (Round 31 landing repair).
pub(crate) fn parse_envelope_head(body: &str) -> Option<EnvelopeParts> {
    let mut scan = HeadScan::new(body);
    scan.skip_ws();
    if !scan.eat(b'{') {
        return None;
    }
    let mut found: Option<EnvelopeParts> = None;
    // Whether the walk accounted for the whole top level
    // object, reaching its closing brace or the end of the
    // text at a key boundary. A walk defeated mid body (a
    // value it could not skip, a key it could not read, an
    // error object that never closed) leaves this false.
    let mut completed = false;
    // Whether the walk cleared an envelope it had found: a
    // later `error` value read whole, an object holding no
    // head field and no details or one that is not an object
    // at all, displaced a usable envelope and left no envelope
    // in its place. The fact is carried on its own because the
    // state it leaves behind, no envelope found and the walk
    // incomplete, is otherwise indistinguishable from having
    // found nothing, and a walk cut short after a clearing
    // must stay as authoritative as a completed one (Round 31
    // landing repair, red team Minor 2).
    let mut cleared = false;
    // The keep rule the scan answers by (A50-009): a head field
    // or a nonempty details array makes the object an envelope.
    let is_envelope = |parts: &EnvelopeParts| {
        parts.status.is_some()
            || parts.message.is_some()
            || parts.code.is_some()
            || !parts.details.is_empty()
    };
    loop {
        scan.skip_ws();
        if scan.at_end() || scan.eat(b'}') {
            completed = true;
            break;
        }
        let Some(key) = scan.string() else {
            break;
        };
        scan.skip_ws();
        if !scan.eat(b':') {
            break;
        }
        scan.skip_ws();
        if key == "error" && scan.peek() == Some(b'{') {
            let (parts, closed) = scan.error_object();
            let usable = is_envelope(&parts);
            if closed || usable {
                if !usable && found.as_ref().is_some_and(is_envelope) {
                    cleared = true;
                }
                if found.is_none() {
                    found = Some(parts);
                }
            }
            if !closed {
                break;
            }
        } else if key == "error" {
            // A later `error` value that is not an object clears
            // the envelope an earlier key found (Round 31,
            // Decoder Minor F1), matching the whole parse reading
            // of the later value. The clear lands only when the
            // value was read whole; a value cut off by the read
            // cap does not erase an earlier complete envelope.
            if scan.skip_value() {
                if found.as_ref().is_some_and(is_envelope) {
                    cleared = true;
                }
                found = None;
            } else {
                break;
            }
        } else if !scan.skip_value() {
            break;
        }
        scan.skip_ws();
        if scan.eat(b',') {
            continue;
        }
        // The object ends here when the next byte is its
        // closing brace; anything else leaves the walk
        // defeated mid body.
        completed = scan.eat(b'}');
        break;
    }
    let found = found.filter(is_envelope);
    if found.is_some() || completed || cleared {
        return found;
    }
    let mut recovery = HeadScan::new(body);
    recovery.recover_envelope()
}

/// The container nesting limit the JSON parser enforces. Its
/// deserializer opens a document with a remaining depth of 128
/// and refuses the container whose opening would spend the last
/// unit, so a body whose bracket nesting reaches 128 open
/// containers anywhere fails the whole document parse with a
/// recursion limit error, whatever else it carries. The value is
/// the parser's own, mirrored here because the parser does not
/// export it.
pub(crate) const RECURSION_DEPTH_LIMIT: usize = 128;

/// The size past which a body's nesting may be walked before its
/// parse is attempted, in [`parse_envelope`] here and in the
/// client's typed decode refusal. The value sits at the error
/// read cap's scale, the largest body this crate reads only to
/// refuse it: at or below it a doomed parse's failure unwind is
/// bounded by the frame count times the size, and past it the
/// structural walk is cheaper than the unwind it replaces by
/// orders of magnitude. Past the size the bracket census in
/// [`preflight_trip`] decides whether the walk runs at all.
pub(crate) const PARSE_PREFLIGHT_MIN_BYTES: usize = 256 * 1024;

/// The count of opening bracket bytes in a body. The parser
/// counts its nesting in containers, every container opens with
/// a bracket byte, and bracket bytes inside strings are content
/// the census counts anyway, so the count can only overstate the
/// nesting a parse can reach, never understate it. A census
/// below [`RECURSION_DEPTH_LIMIT`] is therefore proof that the
/// nesting cannot trip the parser limit.
pub(crate) fn opening_bracket_count(body: &str) -> usize {
    body.bytes()
        .filter(|byte| matches!(byte, b'{' | b'['))
        .count()
}

/// The parse preflight shared by both parse sites: the point
/// where a body's nesting trips the parser recursion limit,
/// when the body is large enough for a doomed parse's unwind to
/// cost more than the walk and its bracket census leaves a trip
/// possible at all. In every other case the parse runs exactly
/// as it did before the preflight existed, so a body's size or
/// its flatness alone never changes which engine judges it
/// (Round 29 landing repair: the first form walked every large
/// body, and large successful responses paid the walk on top of
/// their parses).
pub(crate) fn preflight_trip(body: &str) -> Option<RecursionTrip> {
    if body.len() <= PARSE_PREFLIGHT_MIN_BYTES
        || opening_bracket_count(body) < RECURSION_DEPTH_LIMIT
    {
        return None;
    }
    recursion_trip(body)
}

/// The point where a body's bracket nesting reaches
/// [`RECURSION_DEPTH_LIMIT`], when it does: the byte offset of
/// the bracket that trips the limit, and the field path of the
/// value at that bracket in the rendering the decode error detail
/// uses (wire keys joined by dots, list indices in brackets).
pub(crate) struct RecursionTrip {
    pub(crate) offset: usize,
    pub(crate) path: String,
}

impl RecursionTrip {
    /// The recursion limit message the parser reports for a
    /// failure at this trip point, with the line and column
    /// computed from the body exactly as its slice reader computes
    /// them: the position just past the bracket byte, resolved
    /// against the last newline before it.
    pub(crate) fn message(&self, body: &str) -> String {
        let bytes = body.as_bytes();
        let past = (self.offset + 1).min(bytes.len());
        let start_of_line = bytes[..past]
            .iter()
            .rposition(|byte| *byte == b'\n')
            .map(|found| found + 1)
            .unwrap_or(0);
        let line = 1 + bytes[..start_of_line]
            .iter()
            .filter(|byte| **byte == b'\n')
            .count();
        let column = past - start_of_line;
        format!("recursion limit exceeded at line {line} column {column}")
    }
}

/// Walk a body's bracket structure without building it and
/// report where its nesting reaches [`RECURSION_DEPTH_LIMIT`],
/// when it does.
///
/// The walk is the tolerant head scan's cursor driven by an
/// explicit frame stack, so its cost per byte is the scan's own
/// skip rate. Its tokens are read exactly, under the same
/// grammar the parser applies, so a malformed token ahead of the
/// deep value abstains rather than certifying past it. It proves
/// a negative the callers act on: a body
/// that trips here is a body the whole document parse is
/// guaranteed to refuse with the recursion limit error, so the
/// callers can skip a parse attempt whose failure is certain and
/// whose unwind is priced by the failure (Round 29, Finding 1).
/// The converse is not claimed: a body the walk clears can still
/// fail the parse for any other reason, and the walk abstains
/// with `None` on the first structure it cannot read, so every
/// doubt resolves toward running the parse as before.
///
/// Frame accounting mirrors the parser: the root value's
/// container is the first open frame, and the trip is entering a
/// container while 127 frames are already open. The path is
/// tracked segment by segment as values are entered: an object
/// value under its decoded wire key, an array value under its
/// element index in the parent.
pub(crate) fn recursion_trip(body: &str) -> Option<RecursionTrip> {
    struct Frame {
        object: bool,
        elements: usize,
        key: Option<String>,
    }

    let mut scan = HeadScan::new(body);
    let mut frames: Vec<Frame> = Vec::new();
    // The path segment each open container was itself entered
    // under, innermost last. The root container has none.
    let mut segments: Vec<(bool, String)> = Vec::new();
    'walk: loop {
        // The cursor stands at a value: the root value first,
        // then each child as its parent frame admits it.
        scan.skip_ws();
        let segment: Option<(bool, String)> = match frames.last() {
            None => None,
            Some(frame) if frame.object => Some((false, frame.key.clone()?)),
            Some(frame) => Some((true, format!("[{}]", frame.elements))),
        };
        match scan.peek() {
            Some(b'{' | b'[') => {
                if frames.len() + 1 == RECURSION_DEPTH_LIMIT {
                    let mut path = String::new();
                    for (index, (is_index, text)) in
                        segments.iter().chain(segment.iter()).enumerate()
                    {
                        if *is_index {
                            path.push_str(text);
                        } else {
                            if index > 0 {
                                path.push('.');
                            }
                            path.push_str(text);
                        }
                    }
                    return Some(RecursionTrip {
                        offset: scan.pos,
                        path,
                    });
                }
                let object = scan.peek() == Some(b'{');
                scan.pos += 1;
                if let Some(entered) = segment {
                    segments.push(entered);
                }
                frames.push(Frame {
                    object,
                    elements: 0,
                    key: None,
                });
                scan.skip_ws();
                if object {
                    if scan.eat(b'}') {
                        frames.pop();
                        segments.pop();
                    } else {
                        let key = scan.string()?;
                        scan.skip_ws();
                        if !scan.eat(b':') {
                            return None;
                        }
                        if let Some(frame) = frames.last_mut() {
                            frame.key = Some(key);
                        }
                        continue 'walk;
                    }
                } else if scan.eat(b']') {
                    frames.pop();
                    segments.pop();
                } else {
                    continue 'walk;
                }
            }
            Some(_) => {
                if !scan.skip_scalar() {
                    return None;
                }
            }
            None => return None,
        }
        // A value is complete: account it in its parent frame and
        // advance to the next sibling position, closing containers
        // as they end. The root value completing ends the walk.
        loop {
            let (object, closed, advanced) = {
                let frame = frames.last_mut()?;
                frame.elements += 1;
                scan.skip_ws();
                if frame.object {
                    if scan.eat(b'}') {
                        (true, true, false)
                    } else if scan.eat(b',') {
                        (true, false, true)
                    } else {
                        return None;
                    }
                } else if scan.eat(b']') {
                    (false, true, false)
                } else if scan.eat(b',') {
                    (false, false, true)
                } else {
                    return None;
                }
            };
            if closed {
                frames.pop();
                segments.pop();
                continue;
            }
            if advanced && object {
                scan.skip_ws();
                let key = scan.string()?;
                scan.skip_ws();
                if !scan.eat(b':') {
                    return None;
                }
                if let Some(frame) = frames.last_mut() {
                    frame.key = Some(key);
                }
            }
            break;
        }
    }
}

/// A byte cursor over a response body for the tolerant head scan.
/// Only token boundaries are found by hand; string tokens are
/// decoded by serde_json itself, so escapes and unicode read
/// exactly as the whole parse would read them.
struct HeadScan<'a> {
    bytes: &'a [u8],
    pos: usize,
}

impl<'a> HeadScan<'a> {
    fn new(body: &'a str) -> Self {
        HeadScan {
            bytes: body.as_bytes(),
            pos: 0,
        }
    }

    fn at_end(&self) -> bool {
        self.pos >= self.bytes.len()
    }

    fn peek(&self) -> Option<u8> {
        self.bytes.get(self.pos).copied()
    }

    fn skip_ws(&mut self) {
        while matches!(self.peek(), Some(b' ' | b'\t' | b'\n' | b'\r')) {
            self.pos += 1;
        }
    }

    fn eat(&mut self, byte: u8) -> bool {
        if self.peek() == Some(byte) {
            self.pos += 1;
            true
        } else {
            false
        }
    }

    /// Read one JSON string at the cursor and decode it, or `None`
    /// when the text at the cursor is not a complete decodable
    /// string.
    fn string(&mut self) -> Option<String> {
        self.skip_ws();
        if self.peek() != Some(b'"') {
            return None;
        }
        let start = self.pos;
        self.pos += 1;
        loop {
            match self.peek()? {
                b'\\' => self.pos += 2,
                b'"' => {
                    self.pos += 1;
                    let token = std::str::from_utf8(&self.bytes[start..self.pos]).ok()?;
                    return serde_json::from_str(token).ok();
                }
                _ => self.pos += 1,
            }
        }
    }

    /// Skip the string token at the cursor without decoding it.
    /// Returns false when the token is not complete in the text.
    fn skip_string_raw(&mut self) -> bool {
        // The cursor is on the opening quote.
        self.pos += 1;
        loop {
            match self.peek() {
                None => return false,
                Some(b'\\') => self.pos += 2,
                Some(b'"') => {
                    self.pos += 1;
                    return true;
                }
                Some(_) => self.pos += 1,
            }
        }
    }

    /// Skip one JSON value at the cursor, however deeply nested.
    /// The depth walk is an explicit counter rather than recursion,
    /// so no nesting depth in the skipped value can exhaust it.
    /// Returns false when the value is not complete in the text
    /// (the read was capped) or is malformed.
    fn skip_value(&mut self) -> bool {
        self.skip_ws();
        match self.peek() {
            Some(b'"') => self.skip_string_raw(),
            Some(b'{' | b'[') => {
                let mut depth = 0usize;
                loop {
                    match self.peek() {
                        None => return false,
                        Some(b'"') => {
                            if !self.skip_string_raw() {
                                return false;
                            }
                        }
                        Some(b'{' | b'[') => {
                            depth += 1;
                            self.pos += 1;
                        }
                        Some(b'}' | b']') => {
                            depth -= 1;
                            self.pos += 1;
                            if depth == 0 {
                                return true;
                            }
                        }
                        Some(_) => self.pos += 1,
                    }
                }
            }
            Some(_) => {
                // A number or a true, false or null literal: the
                // token runs to the next structural character or
                // whitespace, neither of which its alphabet holds.
                while matches!(
                    self.peek(),
                    Some(b'0'..=b'9' | b'-' | b'+' | b'.' | b'e' | b'E' | b'a'..=b'z')
                ) {
                    self.pos += 1;
                }
                true
            }
            None => false,
        }
    }

    /// Skip one scalar token at the cursor, exactly as the
    /// parser reads it: a string by
    /// [`HeadScan::skip_string_strict`], a literal by its full
    /// spelling, a number by the JSON number grammar. Anything
    /// else is a failure rather than a skip. The recursion walk
    /// stands at a value it must account for, and a token read
    /// loosely here would let the walk certify a trip past a
    /// malformed token the parser refuses first, so where
    /// `skip_value` tolerates, this refuses.
    fn skip_scalar(&mut self) -> bool {
        match self.peek() {
            Some(b'"') => self.skip_string_strict(),
            Some(b't') => self.skip_literal("true"),
            Some(b'f') => self.skip_literal("false"),
            Some(b'n') => self.skip_literal("null"),
            Some(b'-' | b'0'..=b'9') => self.skip_number(),
            _ => false,
        }
    }

    /// Skip a literal at the cursor by its full spelling. A
    /// longer letter run starting with the spelling is not the
    /// literal, but it needs no special case here: the walk's
    /// structural step after the value meets the extra letters
    /// where a delimiter belongs and abstains there.
    fn skip_literal(&mut self, literal: &str) -> bool {
        if self.bytes[self.pos..].starts_with(literal.as_bytes()) {
            self.pos += literal.len();
            true
        } else {
            false
        }
    }

    /// Skip a number at the cursor under the JSON number
    /// grammar: an optional minus, an integer part that is a
    /// lone zero or a digit run not starting with zero, and
    /// optional fraction and exponent parts that each carry at
    /// least one digit.
    fn skip_number(&mut self) -> bool {
        if self.peek() == Some(b'-') {
            self.pos += 1;
        }
        match self.peek() {
            Some(b'0') => self.pos += 1,
            Some(b'1'..=b'9') => {
                while matches!(self.peek(), Some(b'0'..=b'9')) {
                    self.pos += 1;
                }
            }
            _ => return false,
        }
        if self.peek() == Some(b'.') {
            self.pos += 1;
            if !matches!(self.peek(), Some(b'0'..=b'9')) {
                return false;
            }
            while matches!(self.peek(), Some(b'0'..=b'9')) {
                self.pos += 1;
            }
        }
        if matches!(self.peek(), Some(b'e' | b'E')) {
            self.pos += 1;
            if matches!(self.peek(), Some(b'+' | b'-')) {
                self.pos += 1;
            }
            if !matches!(self.peek(), Some(b'0'..=b'9')) {
                return false;
            }
            while matches!(self.peek(), Some(b'0'..=b'9')) {
                self.pos += 1;
            }
        }
        true
    }

    /// Skip the string token at the cursor, exactly as the
    /// parser reads it. The raw skipper this module uses for
    /// tolerance (`skip_string_raw`) accepts shapes the parser
    /// refuses, which is safe for recovery but not for the
    /// recursion walk's certification, so the walk's strings are
    /// read strictly: an escape must be one of the JSON escapes,
    /// a unicode escape must carry four hex digits with its
    /// surrogate pairing intact, and a raw control character
    /// refuses.
    fn skip_string_strict(&mut self) -> bool {
        if self.peek() != Some(b'"') {
            return false;
        }
        self.pos += 1;
        loop {
            match self.peek() {
                None => return false,
                Some(b'"') => {
                    self.pos += 1;
                    return true;
                }
                Some(b'\\') => {
                    self.pos += 1;
                    match self.peek() {
                        Some(b'"' | b'\\' | b'/' | b'b' | b'f' | b'n' | b'r' | b't') => {
                            self.pos += 1;
                        }
                        Some(b'u') => {
                            self.pos += 1;
                            let Some(unit) = self.hex_unit() else {
                                return false;
                            };
                            if (0xd800..=0xdbff).contains(&unit) {
                                // A leading surrogate stands only
                                // paired with a trailing one.
                                if self.peek() != Some(b'\\') {
                                    return false;
                                }
                                self.pos += 1;
                                if self.peek() != Some(b'u') {
                                    return false;
                                }
                                self.pos += 1;
                                let Some(trailing) = self.hex_unit() else {
                                    return false;
                                };
                                if !(0xdc00..=0xdfff).contains(&trailing) {
                                    return false;
                                }
                            } else if (0xdc00..=0xdfff).contains(&unit) {
                                return false;
                            }
                        }
                        _ => return false,
                    }
                }
                Some(0x00..=0x1f) => return false,
                Some(_) => self.pos += 1,
            }
        }
    }

    /// Read the four hex digits of a unicode escape at the
    /// cursor as its code unit, advancing past them.
    fn hex_unit(&mut self) -> Option<u32> {
        let mut unit: u32 = 0;
        for _ in 0..4 {
            let byte = self.peek()?;
            let digit = match byte {
                b'0'..=b'9' => u32::from(byte - b'0'),
                b'a'..=b'f' => u32::from(byte - b'a') + 10,
                b'A'..=b'F' => u32::from(byte - b'A') + 10,
                _ => return None,
            };
            unit = unit * 16 + digit;
            self.pos += 1;
        }
        Some(unit)
    }

    /// Read the error object's scalar head fields. The cursor is
    /// on the opening brace of the error value; the caller has
    /// already checked that shape, since an `error` value that
    /// is not an object is skipped by the caller rather than
    /// read here. Once the object opens, whatever head fields
    /// were fully read are the result, even when the rest of
    /// the object is truncated or unreadable. The returned flag
    /// says whether the object closed cleanly, which the caller
    /// needs twice over: only a cleanly closed object lets the
    /// top level walk continue on to a later `error` key, and
    /// a message missing from a partly read object was not
    /// shown to be absent.
    ///
    /// A malformed head field costs that field only (Round 31,
    /// Decoder Minor F2). The scan skips malformed values in
    /// unknown keys field by field, and head fields now get the
    /// same posture: a head string that will not decode and a
    /// code token that will not parse lose their own field, the
    /// walk continues, and every well formed head field behind
    /// them still reads. A field lost that way keeps the parts
    /// marked partial even when the object later closes, because
    /// a message read as absent may only be unreadable, which
    /// is exactly what the partial flag exists to say. A value
    /// in an unknown key that cannot be skipped at all (an
    /// unclosed container) still ends the object walk, the
    /// boundary the top level repair of the same round covers
    /// for siblings of the error key.
    ///
    /// Duplicate head keys resolve last wins inside the object
    /// too, as the whole parse resolves them: a repeated field
    /// whose later value is mistyped clears the field, matching
    /// the whole parse reading the later value and skipping it
    /// as mistyped.
    fn error_object(&mut self) -> (EnvelopeParts, bool) {
        self.skip_ws();
        self.eat(b'{');
        let mut parts = EnvelopeParts {
            status: None,
            message: None,
            code: None,
            details: Vec::new(),
            partial: true,
        };
        let mut lost_field = false;
        loop {
            self.skip_ws();
            if self.at_end() {
                return (parts, false);
            }
            if self.eat(b'}') {
                parts.partial = lost_field;
                return (parts, true);
            }
            let Some(key) = self.string() else {
                return (parts, false);
            };
            self.skip_ws();
            if !self.eat(b':') {
                return (parts, false);
            }
            self.skip_ws();
            match key.as_str() {
                "status" | "message" => {
                    let slot = if key == "status" {
                        &mut parts.status
                    } else {
                        &mut parts.message
                    };
                    if self.peek() == Some(b'"') {
                        match self.string() {
                            Some(value) => *slot = Some(value),
                            None => {
                                // The string token was consumed
                                // but would not decode, through
                                // an invalid escape, a lone
                                // surrogate or a raw control
                                // character. The field alone is
                                // lost and the walk continues to
                                // the delimiter below, so a well
                                // formed head field behind it
                                // still reads. A token cut off by
                                // the end of the text has nothing
                                // behind it and ends the object
                                // as before.
                                *slot = None;
                                lost_field = true;
                                if self.at_end() {
                                    return (parts, false);
                                }
                            }
                        }
                    } else {
                        *slot = None;
                        if !self.skip_value() {
                            return (parts, false);
                        }
                    }
                }
                "details" => {
                    if self.peek() == Some(b'[') {
                        // The details recover entry by entry
                        // (Round 41, Finding 4). The scan skips
                        // the array whole to find its span, which
                        // the raw string skipper can do without
                        // decoding anything inside it, and each
                        // entry's text is then parsed on its own,
                        // so an entry the strict parse refuses, a
                        // lone surrogate escape is the proven
                        // shape, costs that entry alone while
                        // clean siblings survive. A poisoned
                        // string elsewhere in the body never
                        // reaches this arm, so it cannot cost the
                        // array. An array the skip cannot complete
                        // (cut off by the read cap) leaves the
                        // surface empty: the whole array fallback
                        // stands when the container itself is
                        // unreadable. A repeated details key
                        // resolves last wins, as the whole parse
                        // resolves it, because each arm overwrites
                        // what an earlier key stored.
                        let start = self.pos;
                        if self.skip_value() {
                            parts.details = details_from_array_text(&self.bytes[start..self.pos]);
                        } else {
                            parts.details = Vec::new();
                            return (parts, false);
                        }
                    } else {
                        parts.details = Vec::new();
                        if !self.skip_value() {
                            return (parts, false);
                        }
                    }
                }
                "code" => match self.peek() {
                    Some(b'0'..=b'9' | b'-') => {
                        let start = self.pos;
                        while matches!(
                            self.peek(),
                            Some(b'0'..=b'9' | b'-' | b'+' | b'.' | b'e' | b'E')
                        ) {
                            self.pos += 1;
                        }
                        let token = std::str::from_utf8(&self.bytes[start..self.pos]).unwrap_or("");
                        match serde_json::from_str::<serde_json::Value>(token) {
                            Ok(value) => parts.code = value.as_i64(),
                            Err(_) => {
                                // The token is not a number at
                                // all (400e and its kin). The
                                // field alone is lost, where the
                                // walk used to end here and take
                                // every field behind it down too.
                                parts.code = None;
                                lost_field = true;
                            }
                        }
                        // Letters trailing the token (the vil
                        // of 400evil, the x of 400x) belong to
                        // the same malformed value. Skip the
                        // scalar run they form so the delimiter
                        // walk below reaches the fields behind
                        // the value instead of ending the
                        // object on them.
                        self.skip_ws();
                        if !matches!(self.peek(), Some(b',' | b'}') | None) {
                            while matches!(
                                self.peek(),
                                Some(
                                    b'0'..=b'9'
                                    | b'-'
                                    | b'+'
                                    | b'.'
                                    | b'e'
                                    | b'E'
                                    | b'a'..=b'z'
                                    | b'A'..=b'Z',
                                )
                            ) {
                                self.pos += 1;
                            }
                            lost_field = true;
                        }
                    }
                    _ => {
                        parts.code = None;
                        if !self.skip_value() {
                            return (parts, false);
                        }
                    }
                },
                _ => {
                    if !self.skip_value() {
                        return (parts, false);
                    }
                }
            }
            self.skip_ws();
            if self.eat(b',') {
                continue;
            }
            // The object ends here when the next byte is its
            // closing brace, which is consumed so the caller's
            // walk resumes past the object; anything else is
            // malformed, and the fields read so far stand
            // either way.
            let closed = self.eat(b'}');
            if closed {
                parts.partial = lost_field;
            }
            return (parts, closed);
        }
    }

    /// One recovery pass over a body whose top level walk found
    /// no usable envelope (Round 31, Decoder Minor F3). The
    /// walk skips a sibling value by counting bracket depth, so
    /// a sibling container that never closes by that count is
    /// never finished and the walk consumes the rest of the
    /// body as part of that value, the error key included. This
    /// pass reads the body again as a flat token stream: it
    /// tracks container depth, skips every string as a unit (so
    /// error text inside a string is never a candidate), and
    /// reads the object behind every `error` key it meets at
    /// depth one or two, keeping the last one that yields a
    /// head field. Depth one is a top level key. Depth two is
    /// where the swallowed key sits, inside the one sibling
    /// whose count went wrong. A key deeper than that is
    /// nested content, and the standing rule that an error
    /// object nested inside a result is not an envelope holds
    /// there.
    ///
    /// Termination and cost: the pass moves forward only. Every
    /// iteration consumes a whole string token, reads one
    /// candidate object in the same forward motion, or advances
    /// one byte, so it ends and it crosses each byte a constant
    /// number of times. It runs at most once per body, only
    /// when the primary walk found nothing and did not complete
    /// its pass over the top level object, and no position is
    /// rescanned beyond it, so the scan's total work on a body
    /// stays linear in the body's size.
    ///
    /// The stated limits of the pass are two. A miscount that
    /// happens to resync onto a later comma lets the primary
    /// walk complete over a swallowed key, and no pass runs
    /// behind a completed walk, so that arrangement stays
    /// unrecovered by design. And the pass cannot tell a
    /// swallowed top level key from an error object nested one
    /// level inside a closed sibling when the walk was defeated
    /// later in the same body, because both present as an
    /// `error` key at depth two on a body the whole parse
    /// refused outright. It adopts the nested object too. The
    /// decoy shapes the earlier rounds held are untouched,
    /// because there a real top level envelope stands behind
    /// the decoy and the primary walk finds it, so this pass
    /// never runs.
    fn recover_envelope(&mut self) -> Option<EnvelopeParts> {
        self.pos = 0;
        let mut depth = 0usize;
        let mut found: Option<EnvelopeParts> = None;
        loop {
            match self.peek() {
                None => break,
                Some(b'"') => {
                    let start = self.pos;
                    if !self.skip_string_raw() {
                        // An unterminated string swallows the
                        // rest of the body in this pass too, and
                        // no key can be read out of it, the same
                        // verdict both engines give it.
                        break;
                    }
                    if depth == 1 || depth == 2 {
                        let is_error = std::str::from_utf8(&self.bytes[start..self.pos])
                            .ok()
                            .and_then(|text| serde_json::from_str::<String>(text).ok())
                            .as_deref()
                            == Some("error");
                        if is_error {
                            let after_string = self.pos;
                            self.skip_ws();
                            if self.eat(b':') {
                                self.skip_ws();
                                if self.peek() == Some(b'{') {
                                    let (parts, closed) = self.error_object();
                                    // The same keep rule as the head
                                    // scan (A50-009). A head field or a
                                    // nonempty details array keeps the
                                    // object.
                                    if parts.status.is_some()
                                        || parts.message.is_some()
                                        || parts.code.is_some()
                                        || !parts.details.is_empty()
                                    {
                                        found = Some(parts);
                                    }
                                    if !closed && self.at_end() {
                                        break;
                                    }
                                    continue;
                                }
                            }
                            self.pos = after_string;
                        }
                    }
                }
                Some(b'{' | b'[') => {
                    depth += 1;
                    self.pos += 1;
                }
                Some(b'}' | b']') => {
                    depth = depth.saturating_sub(1);
                    self.pos += 1;
                }
                Some(_) => self.pos += 1,
            }
        }
        found
    }
}
