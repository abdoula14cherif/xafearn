path = "app/templates/index.html"
html = open(path, encoding="utf-8").read()

old1 = '<div class="play-sub">Mode test — <b>aucun paiement réel</b>, aucune inscription requise</div>'
new1 = '<div class="play-sub">Essai gratuit — <b>crée un compte</b> pour jouer pour de vrai et gagner</div>'
if old1 in html:
    html = html.replace(old1, new1)
    print("✓ mention mode test remplacée")
else:
    print("⚠ bloc 1 non trouvé — vérifie le fichier")

old2 = '''    <div id="endScreen" class="hidden">
      <div class="end-score" id="finalScore">0</div>
      <div class="end-detail" id="finalDetail">points</div>
      <div class="end-rank" id="finalRank"></div>
      <button class="big-btn" onclick="resetGame()">Rejouer</button>
    </div>'''
new2 = '''    <div id="endScreen" class="hidden">
      <div class="end-score" id="finalScore">0</div>
      <div class="end-detail" id="finalDetail">points</div>
      <div class="end-rank" id="finalRank"></div>

      <div class="winners-title">🏆 Ils ont gagné récemment</div>
      <ul class="winners-list">
        <li><span>A. Ngassa</span><span class="w-amt">4 950 F</span></li>
        <li><span>M. Foka</span><span class="w-amt">1 800 F</span></li>
        <li><span>S. Biya</span><span class="w-amt">900 F</span></li>
      </ul>

      <a href="/inscription" class="big-btn" style="display:block; text-decoration:none; box-sizing:border-box;">Créer mon compte pour jouer pour de vrai</a>
    </div>'''
if old2 in html:
    html = html.replace(old2, new2)
    print("✓ écran de fin remplacé")
else:
    print("⚠ bloc 2 non trouvé — vérifie le fichier")

old3 = "  .penalty-note{ font-size:11.5px; color:var(--red); min-height:15px; margin-bottom:4px; }\n</style>"
new3 = '''  .penalty-note{ font-size:11.5px; color:var(--red); min-height:15px; margin-bottom:4px; }
  .winners-title{ font-size:13px; font-weight:700; margin:6px 0 8px; text-align:left; }
  .winners-list{ list-style:none; margin:0 0 18px; padding:0; }
  .winners-list li{
    display:flex; justify-content:space-between; font-size:13px;
    padding:8px 12px; background:var(--card); border-radius:10px; margin-bottom:6px;
  }
  .winners-list .w-amt{ color:var(--green); font-weight:700; font-family:'Space Mono', monospace; }
</style>'''
if old3 in html:
    html = html.replace(old3, new3)
    print("✓ CSS ajouté")
else:
    print("⚠ bloc 3 non trouvé — vérifie le fichier")

open(path, "w", encoding="utf-8").write(html)
print("Fichier mis à jour :", path)
