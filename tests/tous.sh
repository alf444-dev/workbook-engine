#!/usr/bin/env bash
# Toutes les suites. check_cn10_ids exige un ./run.sh préalable sur un manuscrit
# réel ; il est ignoré si output/review.json n'existe pas.
cd "$(dirname "$0")/.."
code=0
for t in test_bundle_ids test_profil test_plan test_generation test_decisions test_server test_admin test_livraison; do
  printf '%-18s ' "$t"
  python3 "tests/$t.py" > /tmp/wb-$t.log 2>&1 && tail -1 /tmp/wb-$t.log || {
    code=1; echo "ÉCHEC"; cat /tmp/wb-$t.log; }
done
printf '%-18s ' check_config
if [ -f content/profile.json ]; then
  python3 pipeline/check_config.py > /tmp/wb-cfg.log 2>&1 && tail -1 /tmp/wb-cfg.log || {
    code=1; echo "ÉCHEC"; cat /tmp/wb-cfg.log; }
else
  echo "ignoré (lancer pipeline/lesson_profile.py d'abord)"
fi
printf '%-18s ' check_lesson
if [ -f content/glossary.json ]; then
  python3 pipeline/check_lesson.py > /tmp/wb-lecon.log 2>&1 && grep 'du livre validé' /tmp/wb-lecon.log | tr -s ' ' || {
    code=1; echo "ÉCHEC"; cat /tmp/wb-lecon.log; }
else
  echo "ignoré (lancer pipeline/glossary.py d'abord)"
fi
printf '%-18s ' check_plan
if [ -f content/plan.json ]; then
  python3 pipeline/check_plan.py > /tmp/wb-plan.log 2>&1 && sed -n '4,5p' /tmp/wb-plan.log | tr -s ' ' || {
    code=1; echo "ÉCHEC"; cat /tmp/wb-plan.log; }
else
  echo "ignoré (lancer pipeline/plan.py d'abord)"
fi
printf '%-18s ' check_cn10_ids
if [ -f output/review.json ]; then
  python3 tests/check_cn10_ids.py > /tmp/wb-cn10.log 2>&1 && tail -1 /tmp/wb-cn10.log || {
    code=1; echo "ÉCHEC"; cat /tmp/wb-cn10.log; }
else
  echo "ignoré (lancer ./run.sh d'abord)"
fi
exit $code
