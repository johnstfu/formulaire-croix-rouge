import streamlit as st
import urllib.parse

st.title("Prendre contact avec la Croix-Rouge")

motif = st.radio(
    "Pourquoi souhaitez-vous prendre contact ?",
    [
        "Besoin d'informations sur les événements Croix-Rouge",
        "Prendre rendez-vous pour un bilan de compétences",
        "Demander un accompagnement administratif",
        "Autre (précisez ci-dessous)"
    ]
)

if motif == "Autre (précisez ci-dessous)":
    autre = st.text_input("Précisez votre demande")
else:
    autre = ""

nom = st.text_input("Votre nom")
email = st.text_input("Votre email")
message = st.text_area("Message complémentaire (facultatif)")

if st.button("Envoyer ma demande par email"):
    sujet = f"Contact via portail Croix-Rouge : {motif}"
    corps = f"Nom : {nom}\nEmail : {email}\n\nMotif : {motif}\n"
    if autre:
        corps += f"Précision : {autre}\n"
    if message:
        corps += f"\nMessage complémentaire : {message}"
    sujet_enc = urllib.parse.quote(sujet)
    corps_enc = urllib.parse.quote(corps)
    mailto_link = f"mailto:rkryslak@albertschool.com?subject={sujet_enc}&body={corps_enc}"
    st.markdown(f"[Cliquez ici pour envoyer votre mail pré-rempli]({mailto_link})")

