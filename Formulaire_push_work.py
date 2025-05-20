# ---------------------------------------------------------------
# Script Streamlit pour le matching Croix-Rouge x France Travail
# À lancer avec : streamlit run Formulaire_push_work.py
# Installe les dépendances dans le terminal avec :
#   pip install streamlit requests notion-client sentence-transformers openai
# ---------------------------------------------------------------

# Formulaire_push_work.py

import streamlit as st
import requests
from notion_client import Client
from sentence_transformers import SentenceTransformer, util
import openai

# --- CONFIGURATION ---
NOTION_TOKEN = "ntn_m175631920120uY8jRs3WvVg6F7Up6bAKZNCaSEgcUX9Et"
NOTION_DATABASE_ID = "1f7068af4de181ceb826e6574645c981"

# France Travail credentials
CLIENT_ID = "PAR_croixrouge_4f8b8a2b1b84f4b9914ce6dc683fd676c1cc8fbe3475a13c9e3246fb0e40eaf3"
CLIENT_SECRET = "ca7c72ae98cf8e1521bd6b0e707c4445eb5a73d55f008235f6ce898fa4c6d058"
SCOPE = "api_offresdemploiv2 o2dsoffre"
URL_TOKEN = "https://entreprise.pole-emploi.fr/connexion/oauth2/access_token?realm=/partenaire"

# --- Codes INSEE pour Paris, Lyon, Marseille ---
paris_codes = {f"Paris {i}": f"75{str(i).zfill(2)}" for i in range(1, 21)}
lyon_codes = {f"Lyon {i}": f"6938{str(i)}" for i in range(1, 10)}
marseille_codes = {f"Marseille {i}": f"132{str(i).zfill(2)}" for i in range(1, 17)}
codes_insee = {**paris_codes, **lyon_codes, **marseille_codes}

# --- 1. Récupération du token France Travail ---
@st.cache_data(ttl=1200)  # 20 minutes
def get_france_travail_token():
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": SCOPE
    }
    response = requests.post(URL_TOKEN, data=data)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        st.error("Erreur lors de la récupération du token France Travail.")
        st.stop()

access_token = get_france_travail_token()

# --- 2. Extraction des profils Notion ---
notion = Client(auth=NOTION_TOKEN)
response = notion.databases.query(database_id=NOTION_DATABASE_ID)
profils = []
for result in response["results"]:
    props = result["properties"]
    profils.append({
        "nom": props["Name"]["title"][0]["plain_text"] if props["Name"]["title"] else "",
        "secteur": props["Secteur Souhaité"]["select"]["name"] if props["Secteur Souhaité"]["select"] else "",
        "ville": props["Location"]["rich_text"][0]["plain_text"] if props["Location"]["rich_text"] else "",
    })

# --- 3. Interface Streamlit ---
st.title("Matching Croix Rouge x France Travail")

profil_selection = st.selectbox("Choisis un profil", [p["nom"] for p in profils])
profil = next(p for p in profils if p["nom"] == profil_selection)
st.write("Secteur souhaité :", profil["secteur"])
st.write("Ville/Arrondissement :", profil["ville"])

type_contrat = st.multiselect("Type de contrat souhaité", ["CDI", "CDD", "Stage", "Alternance"])
teletravail = st.checkbox("Télétravail uniquement")

# --- 4. Recherche d'offres France Travail ---
ville = profil["ville"]
code_insee = codes_insee.get(ville, "75101")  # Par défaut Paris 1er

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}
params = {
    "motsCles": profil["secteur"],
    "commune": code_insee,
    "distance": 10
}
url = "https://api.pole-emploi.io/partenaire/offresdemploi/v2/offres/search"
response = requests.get(url, headers=headers, params=params)
offres = response.json().get("resultats", [])

# --- 5. Matching IA et affichage ---
model = SentenceTransformer('all-MiniLM-L6-v2')
profil_resume = f"{profil['secteur']} {profil['ville']}"
if 'competences' in profil:
    profil_resume += " " + " ".join(profil['competences'])
if 'contrat' in profil:
    profil_resume += " " + profil['contrat']

# Calculer le score IA pour chaque offre
scored_offres = []
for offre in offres:
    offre_resume = f"{offre.get('intitule', '')} {offre.get('description', '')} {offre.get('lieuTravail', {}).get('libelle', '')}"
    score = 0.7 * util.cos_sim(model.encode(profil_resume), model.encode(offre_resume)).item()
    if type_contrat and offre.get('typeContratLibelle') in type_contrat:
        score += 0.3
    scored_offres.append((score, offre))

# Trier par score décroissant
ordre = st.radio("Ordre d'affichage", ["Décroissant (meilleur score en premier)", "Croissant (moins pertinent en premier)"])
reverse = ordre == "Décroissant (meilleur score en premier)"
scored_offres.sort(reverse=reverse, key=lambda x: x[0])

# Afficher uniquement le top 10 des offres selon le score IA
n_top = st.slider("Nombre d'offres à afficher", 1, 20, 10)
top_offres = scored_offres[:n_top]

st.write(f"{len(scored_offres)} offres trouvées pour {profil['nom']} ({ville})")

def expliquer_matching_linkup(profil_resume, offre_resume):
    url = "https://api.linkup.so/v1/search"
    headers = {
        "Authorization": "Bearer d0ef81f8-bd03-4514-833e-e29fb7b19f2f",
        "Content-Type": "application/json"
    }
    data = {
        "q": f"Profil : {profil_resume}\nOffre : {offre_resume}\nExplique en quelques lignes pourquoi cette offre est pertinente pour ce profil, en mettant en avant les points communs.",
        "depth": "standard",
        "outputType": "sourcedAnswer",
        "includeImages": False
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        return result.get("answer") or result.get("output") or str(result)
    else:
        return f"Erreur API Linkup : {response.status_code} - {response.text}"

for score, offre in top_offres:
    offre_resume = f"{offre.get('intitule', '')} {offre.get('description', '')} {offre.get('lieuTravail', {}).get('libelle', '')}"
    st.subheader(offre.get("intitule"))
    st.write("Entreprise :", offre.get("entreprise", {}).get("nom"))
    st.write("Lieu :", offre.get("lieuTravail", {}).get("libelle"))
    st.write("Contrat :", offre.get("typeContratLibelle"))
    st.write("Score IA :", f"{score:.2f}")
    st.write("Lien :", offre.get("origineOffre", {}).get("urlOrigine"))
    st.write("Résumé :", offre.get("description")[:300], "...")
    # Explication IA
    if st.button(f"Pourquoi ce matching ? ({offre.get('intitule')})"):
        explication = expliquer_matching_linkup(profil_resume, offre_resume)
        st.info(explication)
    st.markdown("---")
