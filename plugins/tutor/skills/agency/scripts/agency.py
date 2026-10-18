#!/usr/bin/env python3
"""Agency authority problem generator and answer key.

Builds a fact pattern out of a small set of parameters, then works out the
answer from those parameters alone. The analysis is not the script reasoning
about a story; the story and the analysis are generated from the same settings,
so the key is right by construction.

What the model covers: actual authority (express and implied), apparent
authority, estoppel, ratification, the undisclosed principal, and who is liable
on the contract. Citations are to the Restatement (Third) of Agency (2006).

What the model does NOT cover, and what you should say out loud to a student who
pushes on it: real cases turn on facts a parameter cannot hold -- what exactly
was said, what the trade custom is, what the jury believed. This produces
clean problems for learning a doctrine, not predictions about litigation.

    python agency.py --list
    python agency.py --scenario 4
    python agency.py --scenario 4 --key
    python agency.py --build --context 1 --position general_manager \\
        --grant capped --act 2 --belief position --key
    python agency.py --random --seed 31 --key
"""

import argparse
import random
import sys
import textwrap

# --------------------------------------------------------------------------
# Business settings. Each supplies the cast and three acts of escalating
# magnitude, so the same doctrine can be run in unfamiliar clothing.
# --------------------------------------------------------------------------

CONTEXTS = [
    {
        "principal": "Bowman Foods, Inc.",
        "short": "Bowman",
        "agent": "Rosa Perez",
        "agent_short": "Perez",
        "third": "Dunn Produce Co.",
        "third_short": "Dunn",
        "business": "a regional grocery chain with eleven stores",
        "objective": "keeping the Westheimer store stocked",
        "positions": {
            "general_manager": "general manager of the Westheimer store",
            "sales_rep": "the produce buyer for the Westheimer store",
            "bookkeeper": "a bookkeeper in the back office",
        },
        "acts": {
            1: "placed a $2,000 weekly produce order",
            2: "signed a $40,000 twelve-month supply contract",
            3: "signed a five-year exclusive supply agreement covering all "
               "eleven stores, worth roughly $2.4 million",
        },
        "cap": "$10,000",
        "cap_class": "sign supply contracts",
    },
    {
        "principal": "Calder Equipment LLC",
        "short": "Calder",
        "agent": "Dev Shah",
        "agent_short": "Shah",
        "third": "Ridgeline Contractors",
        "third_short": "Ridgeline",
        "business": "a dealer in construction equipment",
        "objective": "moving inventory off the lot",
        "positions": {
            "general_manager": "sales manager of the Katy lot",
            "sales_rep": "a salesperson on the Katy lot",
            "bookkeeper": "a parts-counter clerk",
        },
        "acts": {
            1: "sold a used skid steer at the posted price",
            2: "sold three excavators at a 15% discount and threw in a "
               "two-year service plan",
            3: "signed an agreement giving the buyer exclusive dealer rights "
               "for the entire Gulf Coast territory",
        },
        "cap": "10%",
        "cap_class": "approve discounts off the posted price",
    },
    {
        "principal": "Alcott Gallery",
        "short": "Alcott",
        "agent": "Iris Novak",
        "agent_short": "Novak",
        "third": "Marta Reyes",
        "third_short": "Reyes",
        "business": "a gallery dealing in twentieth-century prints",
        "objective": "selling the spring inventory",
        "positions": {
            "general_manager": "gallery director",
            "sales_rep": "a floor associate",
            "bookkeeper": "the gallery's registrar",
        },
        "acts": {
            1: "sold a print at the listed price of $1,800",
            2: "sold a print for $22,000 and gave the buyer a written "
               "authenticity guarantee",
            3: "agreed to consign the gallery's entire Rothko holding to the "
               "buyer for resale on commission",
        },
        "cap": "$5,000",
        "cap_class": "approve sales",
    },
    {
        "principal": "Harbor Medical Group",
        "short": "Harbor",
        "agent": "Tom Iverson",
        "agent_short": "Iverson",
        "third": "Vantage Imaging Systems",
        "third_short": "Vantage",
        "business": "a six-clinic physician practice",
        "objective": "keeping the clinics equipped and running",
        "positions": {
            "general_manager": "practice administrator",
            "sales_rep": "the purchasing coordinator",
            "bookkeeper": "a billing clerk",
        },
        "acts": {
            1: "ordered $3,000 of routine imaging supplies",
            2: "signed a $60,000 lease for an ultrasound unit",
            3: "signed a $1.8 million ten-year lease for MRI equipment at all "
               "six clinics",
        },
        "cap": "$25,000",
        "cap_class": "sign equipment leases",
    },
]

POSITION_REACH = {"general_manager": 2, "sales_rep": 2, "bookkeeper": 1, "none": 0}
GRANT_REACH = {"broad": 2, "narrow": 1, "capped": 2, "none": 0}

GRANTS = ("broad", "narrow", "capped", "none")
BELIEFS = ("principal_said", "position", "agent_said", "none")
TERMINATED = ("no", "notice_given", "no_notice")
AFTER = ("nothing", "affirmed", "kept_benefits_knowing",
         "kept_benefits_unknowing", "repudiated")
STATUS = ("disclosed", "unidentified", "undisclosed")


class Incoherent(Exception):
    """The requested combination does not describe a possible situation."""


# --------------------------------------------------------------------------
# Validation. Refusing an impossible combination is itself worth teaching --
# a student who asks for an undisclosed principal whose manifestations the
# third party relied on has not yet seen what "undisclosed" means.
# --------------------------------------------------------------------------

def validate(p):
    if p["status"] == "undisclosed" and p["belief"] in ("principal_said", "position"):
        raise Incoherent(
            "An undisclosed principal is one the third party does not know "
            "exists. The third party cannot have relied on that principal's "
            "statement or on a position that principal conferred. With "
            "--status undisclosed the only coherent beliefs are agent_said "
            "(the third party thought the agent was the owner) or none.")
    if p["status"] == "undisclosed" and p["belief"] == "none":
        raise Incoherent(
            "If the third party had no belief about who they were dealing "
            "with, there is no transaction to analyze. Use --belief agent_said "
            "for the undisclosed-principal case: the third party believed the "
            "agent was contracting on the agent's own account.")
    if p["grant"] == "capped" and p["act"] != 2:
        raise Incoherent(
            "The capped grant exists to put the act just outside the express "
            "limit and squarely inside what the position makes ordinary. That "
            "only works at --act 2. At --act 1 the act is inside the cap and "
            "there is nothing to argue about; at --act 3 nothing supports it.")
    if p["grant"] == "none" and p["terminated"] != "no":
        raise Incoherent(
            "There was no authority to terminate. Use --grant broad or narrow "
            "with --terminated.")
    if p["tp_withdrew"] and p["after"] not in ("affirmed", "kept_benefits_knowing"):
        raise Incoherent(
            "Withdrawal by the third party matters only as a timing defense to "
            "ratification. Pair --tp-withdrew with --after affirmed or "
            "--after kept_benefits_knowing.")
    if p["limit_told_tp"] and p["grant"] not in ("capped", "narrow"):
        raise Incoherent(
            "There is no limit to disclose. Use --grant capped or narrow with "
            "--limit-told-tp.")


# --------------------------------------------------------------------------
# The rules
# --------------------------------------------------------------------------

def actual_authority(p):
    """Restatement (Third) of Agency sections 2.01, 2.02, 3.06, 3.10."""
    if p["grant"] == "none":
        return None, ("The principal made no manifestation to the agent at "
                      "all, so there is nothing for the agent to have "
                      "reasonably believed. Sec. 2.01.")
    if p["terminated"] != "no":
        return None, ("Actual authority ended when the agency relationship "
                      "terminated, whether or not anyone else was told. "
                      "Secs. 3.06, 3.10.")
    if p["grant"] == "capped":
        return None, ("The act exceeds the express limit the principal "
                      "communicated to the agent, so the agent could not "
                      "reasonably believe the principal wished it done. "
                      "Secs. 2.01, 2.02.")
    if p["act"] > GRANT_REACH[p["grant"]]:
        return None, ("The act falls outside the objective the principal "
                      "stated, so it is neither authorized nor incidental to "
                      "anything that was. Sec. 2.02.")
    if p["act"] == 1:
        return "express", ("The act is the very thing the principal told the "
                           "agent to do. Sec. 2.01.")
    return "implied", ("The act is not what the principal named, but it is "
                       "incidental to the objective the principal did name, "
                       "and the agent could reasonably believe it was wanted. "
                       "Sec. 2.02.")


def apparent_authority(p, ctx):
    """Restatement (Third) of Agency sections 1.03, 2.03, 3.11."""
    if p["status"] == "undisclosed":
        return False, ("The third party did not know a principal existed, so "
                       "no belief about a principal's authority was possible. "
                       "Apparent authority is unavailable by definition; the "
                       "question moves to sec. 2.06. Sec. 2.03 cmt. c.")
    if p["belief"] == "none":
        return False, ("The third party had no basis for believing the agent "
                       "had authority. Sec. 2.03.")
    if p["belief"] == "agent_said":
        return False, ("The only source of the third party's belief was the "
                       "agent's own assertion. Apparent authority requires a "
                       "manifestation traceable to the PRINCIPAL. An agent "
                       "cannot confer authority on themselves by claiming it. "
                       "Secs. 1.03, 2.03.")
    if p["belief"] == "position":
        if p["position"] == "none":
            return False, ("There is no position, so there is nothing for the "
                           "principal to have manifested through one. "
                           "Sec. 2.03.")
        if p["act"] > POSITION_REACH[p["position"]]:
            return False, (
                "The principal did place the agent in the position, which is "
                "a manifestation to everyone who deals with the business. But "
                "the act goes beyond what is ordinary for a %s, so the third "
                "party's belief was not reasonable. Sec. 2.03." %
                ctx["positions"][p["position"]])
        basis = ("The principal placed the agent in the position of %s. "
                 "Putting someone in a position is itself a manifestation to "
                 "third parties that the person may do what people in that "
                 "position ordinarily do, and this act is ordinary for it. "
                 "Sec. 1.03 cmt. b, sec. 2.03 cmt. d." %
                 ctx["positions"][p["position"]])
    else:  # principal_said
        if p["act"] == 3:
            return False, ("What the principal said to the third party would "
                           "not lead a reasonable person to expect an act of "
                           "this magnitude. Sec. 2.03.")
        basis = ("The principal made the manifestation to the third party "
                 "directly. Sec. 2.03.")

    if p["limit_told_tp"]:
        return False, ("The third party was told of the limitation. A belief "
                       "held in the face of that is not reasonable, and "
                       "apparent authority cannot exceed what the third party "
                       "reasonably believes. Sec. 2.03.")
    if p["terminated"] == "notice_given":
        return False, ("The third party had notice that the relationship had "
                       "ended, so continued belief was not reasonable. "
                       "Sec. 3.11.")
    if p["terminated"] == "no_notice":
        return True, (basis + " Termination of the relationship did not end "
                      "apparent authority, because the third party had no "
                      "notice of it and it therefore remained reasonable to "
                      "believe what the principal's earlier manifestation "
                      "conveyed. Sec. 3.11.")
    return True, basis


def estoppel(p):
    """Restatement (Third) of Agency section 2.05."""
    if not p["careless"]:
        return False, None
    return True, ("Even without apparent authority, the principal is estopped "
                  "to deny the agent's authority: the principal had notice "
                  "that third parties were likely to be misled and did not "
                  "take reasonable steps to correct it, and the third party "
                  "changed position in reliance. Note the difference from "
                  "apparent authority -- estoppel requires detrimental "
                  "reliance and binds the principal one way only, so the "
                  "principal cannot enforce the contract against the third "
                  "party. Sec. 2.05.")


def ratification(p):
    """Restatement (Third) of Agency sections 4.01-4.07."""
    if p["status"] == "undisclosed":
        return False, ("Only acts taken on a person's behalf as an agent can "
                       "be ratified. The agent here purported to contract on "
                       "their own account, so there is nothing for an "
                       "undisclosed principal to ratify. Sec. 4.03.")
    if p["after"] == "nothing":
        return False, "The principal did nothing after the fact. Sec. 4.01."
    if p["after"] == "repudiated":
        return False, ("The principal repudiated the transaction on learning "
                       "of it, which is the opposite of assent. Sec. 4.01.")
    if p["after"] == "kept_benefits_unknowing":
        return False, ("The principal took the benefit, but without knowledge "
                       "of the material facts. Ratification requires that "
                       "knowledge, so accepting the benefit in ignorance does "
                       "not ratify -- though the principal may still owe "
                       "restitution for what was received. Sec. 4.06.")
    if p["tp_withdrew"]:
        return False, ("The third party withdrew before the principal "
                       "affirmed. Ratification is not effective once the "
                       "third party has withdrawn, because ratification "
                       "relates back and would otherwise let the principal "
                       "hold an option at the third party's expense. "
                       "Sec. 4.05.")
    how = ("expressly affirmed the transaction"
           if p["after"] == "affirmed"
           else "accepted the benefit of the transaction knowing the material "
                "facts, which is conduct justifying a reasonable assumption "
                "of consent")
    return True, ("The principal %s. Ratification relates back: the contract "
                  "is treated as authorized from the moment it was made, not "
                  "from the moment of affirmance. And it is all or nothing -- "
                  "the principal cannot keep the favorable terms and disclaim "
                  "the rest. Secs. 4.01, 4.02, 4.07." % how)


def undisclosed_principal(p):
    """Restatement (Third) of Agency section 2.06."""
    if p["status"] != "undisclosed":
        return False, None
    if p["after"] in ("kept_benefits_knowing", "affirmed") or p["careless"]:
        return True, ("An undisclosed principal may not rely on the agent's "
                      "lack of authority where the principal had notice that "
                      "the agent was dealing with the third party and that "
                      "the third party might be induced to change position, "
                      "and did not take reasonable steps to inform. That is "
                      "this case. Sec. 2.06.")
    return False, ("The undisclosed principal had no notice of the dealing in "
                   "time to stop it, so sec. 2.06 does not reach the "
                   "principal, and no other route to the principal is open. "
                   "Sec. 2.06.")


def agent_exposure(p, bound, actual):
    """Sections 6.01-6.03, 6.10, 8.09."""
    out = []
    if p["status"] == "undisclosed":
        out.append("The agent is a party to the contract in their own right and "
                   "is liable on it, whether or not the principal is also "
                   "reached. Sec. 6.03.")
    elif p["status"] == "unidentified":
        out.append("The principal was disclosed as existing but not "
                   "identified, so the agent is also a party to the contract "
                   "unless the agent and third party agreed otherwise. "
                   "Sec. 6.02.")
    else:
        if bound:
            out.append("The principal is disclosed and bound, so the agent is "
                       "not a party to the contract. Sec. 6.01.")
        else:
            out.append("The principal is not bound, so the agent is liable to "
                       "the third party for breach of the implied warranty of "
                       "authority -- damages measured by what the third party "
                       "would have had if the agent's representation had been "
                       "true. Sec. 6.10.")
    if bound and actual is None:
        out.append("The agent is separately liable to the PRINCIPAL for the "
                   "resulting loss, having acted outside the scope of actual "
                   "authority. That the principal is bound to the third party "
                   "is exactly why the principal has a claim against the "
                   "agent. Sec. 8.09.")
    return out


# --------------------------------------------------------------------------
# Narrative
# --------------------------------------------------------------------------

def narrate(p, ctx):
    title = ctx["positions"].get(p["position"], None)
    s = []
    s.append("%s is %s." % (ctx["principal"], ctx["business"]))

    if p["status"] == "undisclosed":
        s.append("%s runs the business day to day. %s does not hold the "
                 "business out under %s's name, and %s has never heard of %s."
                 % (ctx["agent"], ctx["agent_short"], ctx["principal"],
                    ctx["third"], ctx["principal"]))
    elif p["status"] == "unidentified":
        s.append("%s engaged %s as %s. %s knew %s was acting for some "
                 "company but was never told which one." %
                 (ctx["short"], ctx["agent"], title or "an agent",
                  ctx["third"], ctx["agent_short"]))
    else:
        s.append("%s engaged %s as %s." %
                 (ctx["short"], ctx["agent"], title or "an agent"))

    if p["grant"] == "broad":
        s.append("%s told %s to take charge of %s and to use %s judgment." %
                 (ctx["short"], ctx["agent_short"], ctx["objective"],
                  "their"))
    elif p["grant"] == "narrow":
        s.append("%s's written instructions were specific: %s was to handle "
                 "routine day-to-day matters only, and anything larger was to "
                 "go to the owners." % (ctx["short"], ctx["agent_short"]))
    elif p["grant"] == "capped":
        s.append("%s's written instructions authorized %s to %s up to %s "
                 "and no more." % (ctx["short"], ctx["agent_short"],
                                   ctx["cap_class"], ctx["cap"]))
    else:
        s.append("%s never gave %s any instructions about dealings of this "
                 "kind, one way or the other." %
                 (ctx["short"], ctx["agent_short"]))

    if p["limit_told_tp"]:
        s.append("%s had been told about that limit -- it appears on the "
                 "front of every order form %s signs." %
                 (ctx["third"], ctx["third_short"]))
    elif p["grant"] in ("narrow", "capped"):
        s.append("That instruction was internal. Nothing about it was ever "
                 "communicated to %s." % ctx["third"])

    if p["terminated"] == "notice_given":
        s.append("Three weeks before the events below, %s discharged %s and "
                 "sent written notice of the discharge to %s." %
                 (ctx["short"], ctx["agent_short"], ctx["third"]))
    elif p["terminated"] == "no_notice":
        s.append("Three weeks before the events below, %s discharged %s. No "
                 "one told %s, and %s still had business cards, keys, and "
                 "company letterhead." %
                 (ctx["short"], ctx["agent_short"], ctx["third"],
                  ctx["agent_short"]))

    if p["belief"] == "principal_said":
        s.append("Earlier in the year, an owner of %s had told %s directly "
                 "that %s would be handling this account and that %s should "
                 "deal with %s on it." %
                 (ctx["short"], ctx["third"], ctx["agent_short"],
                  ctx["third_short"], ctx["agent_short"]))
    elif p["belief"] == "position":
        s.append("%s knew %s as %s, and had dealt with %s in that capacity "
                 "before." % (ctx["third"], ctx["agent_short"],
                              title or "an agent", ctx["agent_short"]))
    elif p["belief"] == "agent_said":
        if p["status"] == "undisclosed":
            s.append("%s told %s that the business was %s own and dealt on "
                     "that footing." %
                     (ctx["agent_short"], ctx["third"], "their"))
        else:
            s.append("%s told %s, \"I have full authority to sign this.\" %s "
                     "had no other information about %s's authority and had "
                     "never dealt with %s or %s before." %
                     (ctx["agent_short"], ctx["third"], ctx["third_short"],
                      ctx["agent_short"], ctx["short"], ctx["agent_short"]))
    else:
        s.append("%s and %s had never dealt with each other before, and %s "
                 "made no inquiry about %s's authority." %
                 (ctx["third"], ctx["short"], ctx["third_short"],
                  ctx["agent_short"]))

    if p["careless"]:
        s.append("%s knew that %s was holding %s out this way to customers "
                 "and did nothing about it. %s, relying on the arrangement, "
                 "turned down other business and bought inventory to fill the "
                 "order." % (ctx["short"], ctx["agent_short"], "themselves",
                             ctx["third"]))

    s.append("On March 14, %s, dealing with %s, %s." %
             (ctx["agent"], ctx["third"], ctx["acts"][p["act"]]))

    if p["after"] == "affirmed":
        s.append("When %s learned of the deal, it wrote to %s calling the "
                 "deal a good one and confirming it." %
                 (ctx["short"], ctx["third"]))
    elif p["after"] == "kept_benefits_knowing":
        s.append("%s learned the full terms a week later, said nothing to %s, "
                 "and accepted and used two deliveries under the deal." %
                 (ctx["short"], ctx["third"]))
    elif p["after"] == "kept_benefits_unknowing":
        s.append("%s accepted and used two deliveries under the deal, but no "
                 "one at %s had yet seen the contract or knew what it "
                 "committed them to." % (ctx["short"], ctx["short"]))
    elif p["after"] == "repudiated":
        s.append("%s learned of the deal the next day and immediately told %s "
                 "it would not honor it." % (ctx["short"], ctx["third"]))

    if p["tp_withdrew"]:
        s.append("Note the order of events: %s had already written to %s "
                 "withdrawing from the deal BEFORE %s said anything." %
                 (ctx["third"], ctx["short"], ctx["short"]))

    s.append("")
    s.append("Is %s bound to %s? If so, on what theory? Who else is on the "
             "hook?" % (ctx["principal"], ctx["third"]))
    return s


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

def analyze(p, ctx):
    actual, actual_why = actual_authority(p)
    app, app_why = apparent_authority(p, ctx)
    est, est_why = estoppel(p)
    rat, rat_why = ratification(p)
    und, und_why = undisclosed_principal(p)

    bound = bool(actual) or app or est or rat or und
    if actual:
        theory = "actual authority (%s)" % actual
    elif app:
        theory = "apparent authority"
    elif est:
        theory = "estoppel"
    elif rat:
        theory = "ratification"
    elif und:
        theory = "sec. 2.06, undisclosed principal"
    else:
        theory = None

    lines = []
    lines.append("ANSWER KEY")
    lines.append("=" * 70)
    lines.append("")
    lines.append(_block("ACTUAL AUTHORITY",
                        "YES -- %s" % actual if actual else "NO",
                        actual_why))
    lines.append(_block("APPARENT AUTHORITY", "YES" if app else "NO", app_why))
    if est_why:
        lines.append(_block("ESTOPPEL", "YES", est_why))
    lines.append(_block("RATIFICATION", "YES" if rat else "NO", rat_why))
    if und_why:
        lines.append(_block("UNDISCLOSED PRINCIPAL",
                            "YES" if und else "NO", und_why))
    lines.append("-" * 70)
    if bound:
        lines.append(_wrap("BOTTOM LINE: %s is bound to %s, on %s." %
                           (ctx["principal"], ctx["third"], theory)))
    else:
        lines.append(_wrap("BOTTOM LINE: %s is NOT bound to %s. No route to "
                           "the principal is open." %
                           (ctx["principal"], ctx["third"])))
    lines.append("")
    for note in agent_exposure(p, bound, actual):
        lines.append(_wrap("AGENT: " + note))
        lines.append("")
    return "\n".join(lines)


def _block(label, verdict, why):
    head = "%-22s %s" % (label + ":", verdict)
    if not why:
        return head + "\n"
    return head + "\n" + _wrap(why, indent="    ") + "\n"


def _wrap(text, indent=""):
    # Several of the parties are named "X, Inc." and land at the end of a
    # sentence, so strip the doubled period before wrapping.
    text = text.replace("..", ".")
    return textwrap.fill(text, width=76, initial_indent=indent,
                         subsequent_indent=indent)


def defaults():
    return {
        "context": 0, "position": "general_manager", "grant": "broad",
        "act": 2, "belief": "position", "limit_told_tp": False,
        "terminated": "no", "after": "nothing", "tp_withdrew": False,
        "status": "disclosed", "careless": False,
    }


# --------------------------------------------------------------------------
# Stored scenarios. Each one exists to make a single point; the comment says
# which. Keep them in this order -- they track the module sequence.
# --------------------------------------------------------------------------

SCENARIOS = [
    ("Plain implied actual authority. The warm-up: nothing turns on the "
     "third party at all.",
     dict(context=0, grant="broad", act=2, position="general_manager",
          belief="position")),
    ("The secret limit. Actual authority fails and apparent authority saves "
     "the contract. The single most useful configuration in the whole set.",
     dict(context=0, grant="capped", act=2, position="general_manager",
          belief="position")),
    ("Same secret limit, but the third party was told. Apparent authority "
     "dies the moment the belief stops being reasonable.",
     dict(context=1, grant="capped", act=2, position="general_manager",
          belief="position", limit_told_tp=True)),
    ("The agent's own say-so. The error this whole module exists to kill.",
     dict(context=2, grant="none", act=2, position="sales_rep",
          belief="agent_said")),
    ("Position with reach, act beyond it. Tests whether the student is "
     "checking the position against the act or just noticing there is a "
     "title.",
     dict(context=3, grant="narrow", act=3, position="general_manager",
          belief="position")),
    ("Lingering apparent authority after discharge.",
     dict(context=1, grant="broad", act=2, position="general_manager",
          belief="position", terminated="no_notice")),
    ("Same discharge, notice given. The contrast case for the one above -- "
     "run them back to back.",
     dict(context=1, grant="broad", act=2, position="general_manager",
          belief="position", terminated="notice_given")),
    ("No authority of any kind, then the principal takes the benefit knowing "
     "the facts. Ratification, relating back.",
     dict(context=2, grant="none", act=2, position="sales_rep",
          belief="agent_said", after="kept_benefits_knowing")),
    ("Same, but the principal did not know the material facts. Catches "
     "students who treat any acceptance of benefit as ratification.",
     dict(context=2, grant="none", act=2, position="sales_rep",
          belief="agent_said", after="kept_benefits_unknowing")),
    ("Ratification too late -- the third party withdrew first.",
     dict(context=3, grant="none", act=2, position="bookkeeper",
          belief="agent_said", after="affirmed", tp_withdrew=True)),
    ("Estoppel where apparent authority is unavailable.",
     dict(context=0, grant="none", act=2, position="bookkeeper",
          belief="agent_said", careless=True)),
    ("The undisclosed principal. Sends the student to sec. 2.06 and sec. "
     "6.03 rather than to authority at all.",
     dict(context=1, grant="capped", act=2, position="general_manager",
          belief="agent_said", status="undisclosed",
          after="kept_benefits_knowing")),
    ("Unidentified principal: the agent is on the contract too.",
     dict(context=3, grant="broad", act=2, position="general_manager",
          belief="agent_said", status="unidentified")),
    ("Nothing works. Useful late -- students come to assume every fact "
     "pattern binds somebody.",
     dict(context=2, grant="narrow", act=3, position="bookkeeper",
          belief="none", after="repudiated")),
]


def build_params(overrides):
    p = defaults()
    p.update(overrides)
    validate(p)
    return p


def random_params(rng):
    for _ in range(500):
        p = defaults()
        p.update(
            context=rng.randrange(len(CONTEXTS)),
            position=rng.choice(list(POSITION_REACH)),
            grant=rng.choice(GRANTS),
            act=rng.choice([1, 2, 3]),
            belief=rng.choice(BELIEFS),
            limit_told_tp=rng.random() < 0.25,
            terminated=rng.choice(TERMINATED),
            after=rng.choice(AFTER),
            tp_withdrew=rng.random() < 0.15,
            status=rng.choices(STATUS, weights=[6, 2, 2])[0],
            careless=rng.random() < 0.15,
        )
        try:
            validate(p)
        except Incoherent:
            continue
        return p
    raise SystemExit("could not build a coherent random problem; try another seed")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true",
                    help="list the stored scenarios and what each one teaches")
    ap.add_argument("--scenario", type=int, metavar="N",
                    help="print stored scenario N (1-based)")
    ap.add_argument("--random", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--context", type=int, default=0,
                    help="0-%d" % (len(CONTEXTS) - 1))
    ap.add_argument("--position", choices=list(POSITION_REACH),
                    default="general_manager")
    ap.add_argument("--grant", choices=GRANTS, default="broad")
    ap.add_argument("--act", type=int, choices=[1, 2, 3], default=2)
    ap.add_argument("--belief", choices=BELIEFS, default="position")
    ap.add_argument("--limit-told-tp", action="store_true")
    ap.add_argument("--terminated", choices=TERMINATED, default="no")
    ap.add_argument("--after", choices=AFTER, default="nothing")
    ap.add_argument("--tp-withdrew", action="store_true")
    ap.add_argument("--status", choices=STATUS, default="disclosed")
    ap.add_argument("--careless", action="store_true",
                    help="principal knew of the holding out and let it stand")
    ap.add_argument("--key", action="store_true",
                    help="print the answer key as well as the fact pattern")
    args = ap.parse_args()

    if args.list:
        for i, (why, _) in enumerate(SCENARIOS, start=1):
            print("%2d. %s" % (i, textwrap.fill(
                why, width=72, subsequent_indent="    ")))
        return

    if args.scenario is not None:
        if not 1 <= args.scenario <= len(SCENARIOS):
            raise SystemExit("scenario must be 1-%d" % len(SCENARIOS))
        p = build_params(SCENARIOS[args.scenario - 1][1])
    elif args.random:
        p = random_params(random.Random(args.seed))
    else:
        p = build_params(dict(
            context=args.context, position=args.position, grant=args.grant,
            act=args.act, belief=args.belief,
            limit_told_tp=args.limit_told_tp, terminated=args.terminated,
            after=args.after, tp_withdrew=args.tp_withdrew,
            status=args.status, careless=args.careless))

    ctx = CONTEXTS[p["context"] % len(CONTEXTS)]

    print("FACT PATTERN")
    print("=" * 70)
    print()
    for line in narrate(p, ctx):
        print(_wrap(line) if line else "")
    print()
    if args.key:
        print()
        print(analyze(p, ctx))
        print("-" * 70)
        print("settings: " + " ".join(
            "%s=%s" % (k, v) for k, v in sorted(p.items())))


if __name__ == "__main__":
    try:
        main()
    except Incoherent as e:
        print("That combination does not describe a possible situation.\n",
              file=sys.stderr)
        print(_wrap(str(e)), file=sys.stderr)
        sys.exit(2)
