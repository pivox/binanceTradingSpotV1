# US - Interface UI de controle du daemon

## User Story
**En tant que** utilisateur de l'application  
**Je souhaite** avoir une interface UI pour demarrer et stopper le daemon  
**Afin de** controler l'execution du service sans passer par la ligne de commande.

## Criteres d'acceptation
1. L'UI affiche l'etat courant du daemon (`running` ou `stopped`).
2. L'utilisateur peut demarrer le daemon via un bouton `Demarrer`.
3. L'utilisateur peut stopper le daemon via un bouton `Stopper`.
4. Les actions `Demarrer` et `Stopper` retournent un feedback visuel explicite (succes/erreur).
5. Si le daemon est deja demarre, le bouton `Demarrer` est desactive.
6. Si le daemon est deja stoppe, le bouton `Stopper` est desactive.
7. En cas d'echec (ex: permission, process introuvable), un message d'erreur exploitable est affiche.

## NFR (Non-Fonctionnel)
1. La mise a jour de l'etat dans l'UI apres action doit etre inferieure a 2 secondes.
2. Les commandes de controle du daemon doivent etre journalisees (horodatage, utilisateur, action, resultat).
3. L'acces aux actions de controle doit etre restreint aux utilisateurs autorises.
