<div align="center">
  <img src="assets/readme-banner.svg" alt="SSH Starter — uzak sunucu kontrol paneli" width="100%">
  <br><br>
  <a href="https://github.com/BaranNP/SSH-Starter/releases/latest"><img src="https://img.shields.io/github/v/release/BaranNP/SSH-Starter?display_name=tag&style=for-the-badge&color=9BE36D" alt="En son sürüm"></a>
  <img src="https://img.shields.io/badge/platform-Windows%2010%2B-4B78D1?style=for-the-badge&logo=windows&logoColor=white" alt="Windows 10 ve üzeri">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-9BE36D?style=for-the-badge" alt="MIT lisansı"></a>
  <p><strong>SSH ile bağlan. Uzak programını başlat. Durumunu ve günlüklerini masaüstünden izle.</strong></p>
  <p><a href="https://github.com/BaranNP/SSH-Starter/releases/latest">⬇ En son sürümü indir</a></p>
</div>

SSH Starter, Windows masaüstünden uzak Linux veya Windows bilgisayardaki bir programı SSH ile başlatıp takip etmeni sağlar. Kendi sunucularını ve sık kullandığın görevleri tek bir sade panelden yönet.

## Öne çıkanlar

- **Uzak programı başlat:** Linux çalıştırılabilir dosyalarını, Windows `.exe` ve `.bat` dosyalarını SSH üzerinden çalıştır.
- **Durumunu izle:** Sürecin çalışıp çalışmadığını ve PID bilgisini kontrol et.
- **Günlükleri görüntüle:** Uzak programın standart çıktı ve hata günlüklerini panelden takip et.
- **Bağlantıyı önce test et:** Başlatmadan önce SSH erişimini doğrula.
- **Masaüstü için tasarlandı:** Sürüklenebilir özel başlık çubuğu, yeniden boyutlandırma ve özgün uygulama simgesi.
- **Açılışta başlat:** İsteğe bağlı olarak uygulamanın Windows oturumu açıldığında başlamasını ayarla.

## İndir ve çalıştır

1. [Releases sayfasından](https://github.com/BaranNP/SSH-Starter/releases/latest) `SSHStarter.exe` dosyasını indir.
2. EXE'yi Windows bilgisayarında çalıştır. Python kurulumu gerekmez.
3. Uygulamada SSH sunucusu, kullanıcı adı ve hedef sistem bilgilerini gir.
4. Uzak dosyanın tam yolunu belirt. Örneğin `/opt/my-app/server` veya `C:\Apps\my-app\server.exe`.
5. **SSH bağlantısını test et** düğmesiyle bağlantıyı doğrula, ardından **Başlat** düğmesine bas.

Windows'ta OpenSSH Client kurulu olmalıdır. Kurulumu PowerShell'de `ssh -V` komutuyla kontrol edebilirsin. Linux hedefinde dosyanın çalıştırma izni olmalıdır.

## Bağlantı ve kullanım

SSH kullanıcı adı ve portu arayüzden girilebilir. İstersen bilgisayarındaki `%USERPROFILE%\.ssh\config` dosyasına bir sunucu takma adı ekleyip uygulamada bu adı kullanabilirsin:

```sshconfig
Host uygulama-sunucum
    HostName sunucu-adresi
    User deploy
    Port 22
    IdentityFile ~/.ssh/id_ed25519
```

Bağlantı kurulduktan sonra **Başlat** uzak programı çalıştırır; kontrol paneli süreç durumunu, PID'yi ve günlükleri gösterir. **Durdur** izlenen süreci kapatır.

## Güvenlik

- Kimlik doğrulaması bilgisayarındaki OpenSSH istemcisiyle yapılır. Parola veya özel anahtar uygulamaya gömülmez.
- Uzak program, SSH hesabının yetkileriyle çalışır. Yalnızca güvendiğin sunuculara bağlan.
- Sunucu adresini, dosya yolunu ve argümanları başlatmadan önce kontrol et.
- SSH Starter uzak sunucuna arka kapı veya ayrı bir servis kurmaz; işlemleri SSH oturumu üzerinden yürütür.

## Sorun giderme

- **SSH bulunamadı:** Windows özelliklerinden OpenSSH Client'ı kur ve `ssh -V` ile doğrula.
- **Bağlantı kurulamıyor:** Aynı adresle terminalde `ssh kullanıcı@sunucu` komutunu dene; kullanıcı, port, anahtar ve sunucu güvenlik duvarını kontrol et.
- **Program başlamıyor:** Uzak dosya yolunun doğru olduğunu ve Linux'ta çalıştırma izni bulunduğunu doğrula.
- **Günlük görünmüyor:** Programın stdout veya stderr akışına yazdığını kontrol et.

## Lisans ve geliştirici

MIT lisansı için [`LICENSE`](LICENSE) dosyasına bak.

**Geliştirici:** [Baran Alaçam](https://github.com/BaranNP)
