lxc ls | grep -v "NAME" | grep -v "-" | awk '$2!="|" {print "lxc delete " $2 " --force"}' > $$ && sh $$
lxc network ls | grep -v "NAME" | grep -v "-" | awk '$2!="|" {print "lxc network delete " $2 }' > $$ && sh $$
rm $$
