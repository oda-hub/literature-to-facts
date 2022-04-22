install-service:
	install l2f-daily.service $(HOME)/.config/systemd/user/l2f-daily.service
	systemctl --user daemon-reload
	systemctl --user restart l2f-daily.service

follow-service-log:
	journalctl --user -u l2f-daily.service --follow
