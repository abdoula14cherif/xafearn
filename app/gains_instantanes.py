# Part du ticket réservée au gain instantané (le reste alimente la cagnotte du classement)
POURCENTAGE_INSTANT = 0.20
# Nombre maximum de bonnes réponses récompensées instantanément par partie
PLAFOND_BONNES_REPONSES = 25

def calculer_reward_par_bonne_reponse(montant):
    budget_instant = round(montant * POURCENTAGE_INSTANT)
    return max(1, budget_instant // PLAFOND_BONNES_REPONSES)

def calculer_gain_instantane(montant, correct_count):
    reward = calculer_reward_par_bonne_reponse(montant)
    reponses_recompensees = min(correct_count, PLAFOND_BONNES_REPONSES)
    return reponses_recompensees * reward

def calculer_part_cagnotte(montant):
    return montant - round(montant * POURCENTAGE_INSTANT)
