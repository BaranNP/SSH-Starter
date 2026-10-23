# SSH Starter

SSH Starter, Windows masaüstünden SSH bağlantısıyla uzak Linux veya Windows bilgisayardaki bir programı başlatıp durumunu ve günlüklerini izlemenizi sağlar.

## İndirip çalıştırma

1. `SSHStarter.exe` dosyasını indirin.
2. Windows bilgisayarınızda OpenSSH Client'ın kurulu olduğunu doğrulayın (`ssh -V`).
3. Uygulamayı çalıştırın. Windows SmartScreen uyarısı gösterirse yayımlayanı ve dosyanın kaynağını doğruladıktan sonra devam edin.
4. SSH sunucusu, kullanıcı, hedef işletim sistemi ve uzak dosya yolunu girin.
5. Bağlantıyı test edin ve **Başlat** düğmesine basın.

Uygulama Python gerektirmeyen, Windows 10 ve üzeri için paketlenmiş bir masaüstü uygulamasıdır. Uzak sunucuda uygun SSH erişimi ve Linux'ta çalıştırılabilir dosya izni gerekir.

## Güvenlik

Uygulama yerel OpenSSH istemcisini kullanır; SSH parolası veya özel anahtar uygulamaya gömülmez. Uzak program, SSH hesabının yetkileriyle çalışır. Yalnızca güvendiğiniz sunuculara bağlanın.

## Lisans

MIT Lisansı. Ayrıntılar için bu depodaki [`LICENSE`](LICENSE) dosyasına bakın.

## Geliştirici

Baran Alaçam · [GitHub](https://github.com/BaranNP)
