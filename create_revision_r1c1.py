"""
Reviewer 1, Comment 1: Condense the abstract for conciseness (~15-20% shorter)
while preserving all key findings.
"""
import json

old_abstract = (
    "Black alder (Alnus glutinosa), the phyllophagous leaf beetle (Agelastica alni), "
    "the koinobiont larval endoparasitoid (Meigenia mutabilis), and generalist passeriform "
    "birds constitute an ecoepidemic system across alluvial forests in Europe. Phyllophagy "
    "by beetle larvae causes foliar biomass loss in the tree. The endoparasitoid parasitises "
    "susceptible beetle larvae by ovipositing on their integument; emergence of adult "
    "parasitoids kills parasitised larvae, providing natural regulation of defoliation. "
    "Generalist passeriform birds, following optimal foraging strategies, also contribute to "
    "biocontrol by preferentially consuming the most abundant prey during outbreaks. Induced "
    "phytochemical changes in pest-infected trees provide stand-level resistance that may "
    "accumulate and persist into the subsequent year. Thus, resistance differs across "
    "intra-annual and interannual timescales, while vernal regrowth, providing system "
    "resilience via canopy recovery, is observable only at an annual timescale. This temporal "
    "discordance introduces complexity in system stability. This study uses a process-based "
    "hybrid seasonal\u2013annual model of this focal ecoepidemic system to quantify how resistance "
    "and resilience jointly structure stability across nine phenological scenarios associated "
    "with climatic variation, and applies optimal control theory to contrast three pest-management "
    "strategies. Results show that the coexistence equilibrium is the least frequently stable "
    "regime across phenological parameter space, while the parasitoid-free state is the most "
    "frequent. When all phenological parameters vary simultaneously, the probability of regime "
    "shift from coexistence reaches 81.5%. Among the three management strategies tested, only "
    "the fully integrated strategy combining parasitoid augmentation, targeted larval removal, "
    "and bird-habitat enhancement achieves a locally stable managed equilibrium and does so at "
    "minimum cost. These findings indicate that maintaining parasitoid-based biological control "
    "requires active, multi-component intervention and that single-agent strategies, though "
    "capable of short-term suppression, fail to ensure long-term system stability."
)

new_abstract = (
    "Black alder (Alnus glutinosa), the phyllophagous leaf beetle (Agelastica alni), "
    "the koinobiont larval endoparasitoid (Meigenia mutabilis), and generalist passeriform "
    "birds form an ecoepidemic system in European alluvial forests. The endoparasitoid "
    "parasitises susceptible beetle larvae, and its emergence kills them, providing natural "
    "regulation of defoliation. Generalist birds contribute additional biocontrol by "
    "preferentially consuming the most abundant prey during outbreaks. Induced phytochemical "
    "changes confer stand-level resistance that may persist into the subsequent year, whereas "
    "vernal regrowth provides system resilience via canopy recovery only at an annual timescale. "
    "This temporal discordance introduces complexity in system stability. Using a process-based "
    "hybrid seasonal\u2013annual model, we quantify how resistance and resilience jointly structure "
    "stability across nine phenological scenarios associated with climatic variation and apply "
    "optimal control theory to contrast three pest-management strategies. Results show that the "
    "coexistence equilibrium is the least frequently stable regime across phenological parameter "
    "space, while the parasitoid-free state is the most frequent. When all phenological "
    "parameters vary simultaneously, the probability of regime shift from coexistence reaches "
    "81.5%. Among the three strategies tested, only the fully integrated strategy combining "
    "parasitoid augmentation, targeted larval removal, and bird-habitat enhancement achieves "
    "a locally stable managed equilibrium at minimum cost. These findings demonstrate that "
    "maintaining parasitoid-based biological control requires active, multi-component "
    "intervention, as single-agent strategies fail to ensure long-term system stability."
)

old_words = len(old_abstract.split())
new_words = len(new_abstract.split())
reduction = (old_words - new_words) / old_words * 100

print(f"Old abstract: {old_words} words")
print(f"New abstract: {new_words} words")
print(f"Reduction: {reduction:.1f}%")

revision = {
    "old": old_abstract,
    "new": new_abstract,
    "comment": "Reviewer 1, Comment 1: Abstract condensed for conciseness as requested."
}

with open("revision_r1c1.json", "w", encoding="utf-8") as f:
    json.dump(revision, f, indent=2, ensure_ascii=False)

print("Saved revision_r1c1.json")
