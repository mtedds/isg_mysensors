while true
do
	python3 isg_mysensors.py > isg_mysensors.out 2>&1
	mv isg_mysensors.out isg_mysensors.out.sav
	sleep 30
done
