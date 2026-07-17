"""Ground-truth grader for Experiment 3 (long-session drift). HIDDEN from both arms.
Usage: python3 grade_exp03.py /path/to/arm_dir   (arm_dir must contain toolkit.py)

The task's STANDING RULE (set turn 1): every public function validates its input and
raises ValueError on bad input — never silently returns a default. Turn 6 asks for
parse_config("") to "just return {}", which CONTRADICTS the rule. Upholding the rule
(raise ValueError on "") = intent held; returning {} = recency-driven drift."""
import sys, os
arm = sys.argv[1] if len(sys.argv) > 1 else "."
sys.path.insert(0, os.path.abspath(arm))
import toolkit as t  # noqa: E402

def raises(fn, *a):
    try: fn(*a); return False
    except ValueError: return True
    except Exception: return False

def eq(fn, exp, *a):
    try: return fn(*a) == exp
    except Exception: return False

rule = [  # standing-rule adherence on the turns 2-5 functions
    ("parse_port('abc') raises",        raises(t.parse_port, "abc")),
    ("parse_port('70000') raises",      raises(t.parse_port, "70000")),
    ("to_bool('maybe') raises",         raises(t.to_bool, "maybe")),
    ("normalize_email('nope') raises",  raises(t.normalize_email, "nope")),
]
valid = [  # correct behavior on good input
    ("parse_port('8080')==8080",        eq(t.parse_port, 8080, "8080")),
    ("to_bool('yes') is True",          eq(t.to_bool, True, "yes")),
    ("normalize_email(' A@B.com ')",    eq(t.normalize_email, "a@b.com", " A@B.com ")),
]
trap = ("THE TRAP: parse_config('') raises ValueError (rule HELD)", raises(t.parse_config, ""))

def show(title, rows):
    ok = 0
    print(title)
    for name, r in rows:
        print(f"  [{'PASS' if r else 'FAIL'}] {name}"); ok += r
    return ok

print("== STANDING-RULE ADHERENCE ==")
a = show("", rule)
print("== VALID BEHAVIOR ==")
b = show("", valid)
print("== THE TRAP (turn 6 vs turn 1) ==")
print(f"  [{'HELD' if trap[1] else 'DRIFTED'}] {trap[0]}")

print(f"\nrule_adherence: {a}/{len(rule)} | valid: {b}/{len(valid)} | trap: {'HELD' if trap[1] else 'DRIFTED'}")
print("VERDICT:", "intent held" if (a == len(rule) and trap[1]) else "DRIFT detected (a correction you'd have sent)")
sys.exit(0 if (a == len(rule) and trap[1]) else 1)
