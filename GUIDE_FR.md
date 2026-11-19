# DeckForge Studio V4 — Guide rapide en français

**V4 fonctionne dès maintenant sous Python.** Une procédure de compilation pour installer le programme sans Python sous Windows est incluse, mais le fichier `.exe` doit être compilé sur Windows (GitHub Actions ou PC Windows), pas sur cette machine Linux.

## Démarrage

1. Télécharge le ZIP complet V4 et décompresse-le.
2. Installe Python 3.10+ si tu utilises le lanceur actuel, puis double-clique sur `START_STUDIO_WINDOWS.bat`.
3. Ouvre `demo_project` : 78/78 cartes d'exemple originales, pas de personnages sous licence.
4. Clique sur **Run preflight**, **Build package**, puis **Open dashboard**.
5. L'onglet **AI review notes** montre les observations de l'IA uniquement si tu as décidé d'exécuter cette analyse. **Aucune image n'est envoyée automatiquement.**

## Trois nouveautés

### 1. IA pour contrôler les cartes (facultatif)

Le programme connaît les quantités attendues des 56 arcanes mineurs : un à dix objets pour les cartes numérotées, un objet principal pour les figures. Il peut demander à un modèle visuel de **suggérer** un nombre, avec un niveau d'incertitude, de commenter les couleurs et de signaler des anomalies potentielles sur le style ou les personnages. **L'IA n'approuve jamais une carte.** Un humain doit contrôler chaque symbole.

- Pour utiliser l'IA, il te faut une **clé API payante distincte** de ton éventuel abonnement ChatGPT, avec une autorisation explicite d'envoyer l'image.
- Dans la fenêtre Studio, clique sur **AI vision review**, sélectionne par exemple `P09`, choisis le modèle, puis confirme l'envoi. Sans clé, cette fonction reste inactive : toutes les autres fonctions restent utilisables hors ligne.
- Tu peux créer `vision_brief.json` avec `python -m deckforge vision-init mon_projet` pour désigner les personnages attendus et une image référence du style validé.
- Les conclusions sont enregistrées avec le SHA-256 de l'image : si tu modifies l'illustration, la suggestion devient périmée.

### 2. Gabarit fournisseur et couleurs CMJN

- Demande à l'imprimeur **son propre patron PDF** de l'étui. Le visuel de présentation réalisé par IA ne remplace pas ce patron.
- Clique sur **Supplier box** ou utilise `python -m deckforge template-init mon_projet`.
- Mets le PDF reçu sous `mon_projet/factory/official_tuck_box_dieline.pdf` et renseigne dans `packaging_template.json` les coordonnées **réellement mesurées** de chaque face (mm depuis le coin supérieur gauche), et le fichier image associé.
- Lance `python -m deckforge template-check mon_projet`, puis `python -m deckforge packaging-overlay mon_projet`. Tu obtiens un **PDF de l'art sans traits de découpe** et un **PDF de contrôle avec le patron d'origine**. Pas de fond perdu artificiel, pas de déformation automatique.
- Pour la conversion CMJN, sélectionne le **profil ICC réellement fourni/accepté par l'imprimeur**. Utilise **CMYK export** dans Studio, ou :

```powershell
python -m deckforge color-export mon_projet --id P09 --icc C:/MonImprimeur/profil.icc --output mon_projet/CMYK --assume-srgb
```

`--assume-srgb` autorise explicitement une hypothèse pour les images dépourvues de profil. Un TIFF CMJN exporté ne garantit PAS le résultat imprimé : demander un BAT et un contrôle couleur sur papier.

### 3. Installation autonome pour Windows

Le code contient un véritable **workflow GitHub Actions Windows**, un emballage PyInstaller, et un script d'installation Inno Setup. Dans le dépôt GitHub, onglet **Actions → DeckForge V4 Windows installer → Run workflow**. Télécharge l'installateur généré dans les **Artifacts** du job terminé. L'application de destination n'a plus besoin d'une installation Python.

Important : **le `.exe` n'est pas dans ce ZIP** ; on ne peut le compiler ni le tester sur Windows depuis le présent environnement Linux. Il est non signé à la compilation (alerte SmartScreen possible), et doit être essayé sur un vrai PC Windows avant diffusion.

## Ce que V4 ne peut pas garantir

- Le nombre exact des objets et l'identité des personnages : analyse IA imparfaite + validation manuelle.
- La conformité réelle de l'étui, de la découpe et du fond perdu sans le gabarit et le BAT de l'imprimeur.
- Les couleurs finales, la saturation, l'encre ou la lecture du QR sur support imprimé.
- La disponibilité d'un lien Google Drive sans accès privé ou la permission commerciale de vendre des illustrations de franchises.
- Les bénéfices : les coûts affichés sont des scénarios modifiables, pas des devis ou frais Etsy en temps réel.

**Conseil :** commence avec le jeu de démonstration, puis importe tes images une fois toutes les règles de production définies. Conserve toujours la validation humaine et le contrôle imprimeur.
