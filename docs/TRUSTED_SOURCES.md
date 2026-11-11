# Danh mục nguồn web đã rà soát

Rà soát ngày **06/11/2026**. Cấu hình chạy tại `configs/web_retrieval.yaml` tăng từ
**47 lên 234 hostname**, thêm **187**. Có
**150 mục cơ quan/ấn phẩm** theo tên; các địa chỉ `www`, địa chỉ cũ chuyển
hướng và chuyên trang có thể thuộc cùng một nhà xuất bản. Đây không phải 234 tờ báo độc lập.

| Nhóm | Hostname được phép |
| --- | ---: |
| Cơ quan nhà nước, dữ liệu và pháp luật | 61 |
| Báo, đài và tạp chí | 135 |
| Tổ chức quốc tế và khoa học | 20 |
| Nguồn công bố trực tiếp của doanh nghiệp | 18 |

## Tiêu chí lựa chọn và phạm vi

- Đối chiếu tên cơ quan, ấn phẩm trên website chính thức hoặc danh bạ chính thức;
  thử DNS, HTTPS và chuyển hướng. Chỉ thêm từng hostname chính xác, không dùng wildcard.
- Nguồn nhà nước phù hợp với văn bản, thông báo và số liệu thuộc thẩm quyền.
  Báo chí cung cấp tin có ngày và nội dung bài gốc. Số liệu quốc tế ưu tiên cơ quan công bố.
- Nguồn doanh nghiệp như NVIDIA, Samsung, TSMC, Google và Microsoft chỉ phù hợp
  với công bố về chính họ; các khẳng định đánh giá rộng hơn cần đối chiếu độc lập.
- Có tên trong allowlist không đồng nghĩa bài viết đúng hoặc đủ để kết luận.
  Vẫn kiểm tra thực thể, ngày, nội dung đầy đủ, quan hệ bằng chứng và trích dẫn.
- Danh tính đã xác minh và khả năng tải hiện tại là hai trạng thái riêng.
  Một số trang chính thức chặn bot, lỗi HTTPS hoặc lặp chuyển hướng. Chúng được
  ghi rõ trong báo cáo; runtime vẫn tuân thủ robots.txt, chứng chỉ và kiểm tra
  redirect. Không dùng snippet RSS hay kết quả tìm kiếm thay nội dung bài gốc.
- Nguồn cũ trong 47 hostname được ghi `preexisting_allowlist` nếu đợt này chưa
  kiểm lại được danh tính qua nội dung trang. Nguồn mới phải có đối chiếu danh tính.

Nguồn tham chiếu công khai đã dùng để rà soát gồm [danh bạ Chính phủ](https://chinhphu.vn/),
[Bộ Khoa học và Công nghệ](https://mst.gov.vn/), [WHO](https://www.who.int/about),
[World Bank](https://www.worldbank.org/ext/en/who-we-are), [IMF](https://www.imf.org/en/about),
[ADB](https://www.adb.org/who-we-are), [OECD](https://www.oecd.org/en/about.html),
[UNDP](https://www.undp.org/about-us), [IPCC](https://www.ipcc.ch/about/structure/) và
thông tin cơ quan chủ quản/giấy phép trên từng báo.

## Khám phá bài mới bằng RSS/sitemap

Bổ sung **144 endpoint XML đã tải và phân tích thành công**, nâng danh mục lên
**152 URL** gồm 8 URL cơ sở. Trong lần rà soát, **151/152 URL cấu hình** đọc được,
thuộc **37 hostname nhà xuất bản** sau khi gộp `www`; một URL cơ sở cũ chưa đọc được.
RSS/sitemap chủ yếu giúp phát hiện bài mới, không bao phủ toàn bộ bài lịch sử.

Mỗi phát biểu chọn tối đa **12 kênh** từ danh mục: 4 kênh tin chung của VnExpress,
Công lý, Dân Trí và Tuổi Trẻ, sau đó ưu tiên chủ đề và địa phương khớp, giữ đa dạng
nhà xuất bản. Chỗ trống ưu tiên kênh tổng hợp trước chuyên mục không liên quan.
Thứ tự đồng hạng được xoay ổn định theo phát biểu, để các nguồn mới có cơ hội được chọn.
Tải tối đa 6 kênh song song, timeout mỗi kênh 4 giây, cache 5 phút. Sitemap ngày
có giới hạn riêng như cấu hình cũ. Các giới hạn Tavily, quota và tải bài gốc giữ nguyên.

Không tải toàn bộ 152 kênh cho mỗi phát biểu. `web_attempts` trong Chi tiết kỹ thuật
cho biết `feed_pool_size`, kênh đã chọn, lỗi tải và số ứng viên. Việc tăng nguồn chưa
tự chứng minh Recall@k tốt hơn; cần đo trên tập giữ riêng có bài gốc và đoạn bằng chứng.

## Hồ sơ kiểm tra

- [Danh tính, HTTPS, redirect và lỗi từng hostname](../data/source_catalog/source_review_20261106.json).
- [Kết quả đọc RSS/sitemap từng endpoint](../data/source_catalog/feed_review_20261106.json).
- [Lượt thử tự tìm bài gốc, không dùng URL đáp án](../data/source_catalog/retrieval_smoke_20261106.json).
- [Quy trình truy xuất và đo tự tìm nguồn](NEWS_RETRIEVAL_FIX.md).

Các báo cáo chỉ lưu metadata kiểm tra, không chứa API key hay nội dung toàn bài.
Những địa chỉ chưa xác minh danh tính, trang giả/aggregator không rõ trách nhiệm,
alias lỗi chứng chỉ chưa đối chiếu hoặc chuyển sang host lạ không được tự động thêm.

Kiểm tra sau khi cập nhật: **209 passed, 2 xfailed** trong nhóm hồi quy retrieval,
cấu hình và dựng hệ thống. Lượt thử trực tiếp ngày 06/11/2026 cho claim Kim Liên
tìm được bài liên quan của Dân Trí, Tuổi Trẻ và Báo Xây dựng, đọc được đoạn từ trang gốc.
Claim AI/chip tự tìm đúng bài Báo Văn Hóa ở vị trí đầu sau hai lượt Tavily;
RSS riêng trong lượt thử đó chưa tìm đúng bài. Các lượt này không truyền URL
đáp án, không gọi verifier và không đo độ chính xác kết luận hay recall tổng quát.

## Danh mục đang cấu hình

Liên kết dưới đây mở website hoặc trang tham chiếu danh tính; không cam kết mọi
trang đang tải được. Chi tiết khả dụng nằm trong báo cáo JSON.

### Cơ quan nhà nước, dữ liệu và pháp luật

| Cơ quan/ấn phẩm | Hostname | Phạm vi |
| --- | --- | --- |
| [Báo Điện tử Chính phủ](https://baochinhphu.vn/) | `baochinhphu.vn`, `www.baochinhphu.vn` | Thông tin, chính sách và thông báo của Chính phủ |
| [Bộ Công an](https://bocongan.gov.vn/) | `bocongan.gov.vn`, `www.bocongan.gov.vn` | Thông cáo và cảnh báo chính thức |
| [Bộ Công Thương](https://moit.gov.vn/) | `moit.gov.vn` | Điều hành giá xăng dầu, thương mại, công nghiệp |
| [Bộ Giáo dục và Đào tạo](https://moet.gov.vn/) | `moet.gov.vn` | Giáo dục, tuyển sinh và văn bản của Bộ |
| [Bộ Khoa học và Công nghệ](https://mst.gov.vn/) | `mst.gov.vn` | Khoa học, công nghệ, đổi mới sáng tạo và chuyển đổi số |
| [Bộ Ngoại giao](https://mofa.gov.vn/) | `mofa.gov.vn`, `www.mofa.gov.vn` | Thông cáo, bảo hộ công dân và thông tin đối ngoại chính thức |
| [Bộ Nông nghiệp và Môi trường](https://mae.gov.vn/) | `mae.gov.vn` | Nông nghiệp, môi trường và công bố chính thức |
| [Bộ Tài chính](https://mof.gov.vn/) | `mof.gov.vn`, `www.mof.gov.vn` | Tài chính, thuế, giá |
| [Bộ Tư pháp](https://moj.gov.vn/) | `moj.gov.vn`, `www.moj.gov.vn` | Pháp luật và hướng dẫn chính thức |
| [Bộ Văn hóa, Thể thao và Du lịch](https://bvhttdl.gov.vn/) | `bvhttdl.gov.vn` | Văn hóa, thể thao và du lịch |
| [Bộ Y tế](https://moh.gov.vn/) | `moh.gov.vn` | Chính sách, hướng dẫn và thông báo y tế chính thức |
| [Công báo điện tử](https://congbao.chinhphu.vn/) | `congbao.chinhphu.vn` | Công bố văn bản; đối chiếu bản gốc và hiệu lực |
| [Cơ quan Hải quan Việt Nam](https://customs.gov.vn/) | `customs.gov.vn`, `www.customs.gov.vn` | Số liệu xuất nhập khẩu và thông báo hải quan |
| [Cơ quan Khí tượng Nhật Bản](https://www.jma.go.jp/) | `www.jma.go.jp` | Cảnh báo thiên tai và thông tin JMA |
| [Cơ quan Thuế Việt Nam](https://www.gdt.gov.vn/) | `www.gdt.gov.vn` | Thông báo thuế và hướng dẫn chính thức |
| [Cơ sở dữ liệu quốc gia về văn bản pháp luật](https://vbpl.vn/) | `vbpl.vn` | Văn bản pháp luật; kiểm hiệu lực và văn bản gốc |
| [Cổng thông tin Cần Thơ](https://cantho.gov.vn/) | `cantho.gov.vn`, `www.cantho.gov.vn` | Thông tin chính quyền địa phương và thông báo công cộng |
| [Cổng thông tin Huế](https://hue.gov.vn/) | `hue.gov.vn` | Thông tin chính quyền địa phương và thông báo công cộng |
| [Cổng thông tin Hà Nội](https://hanoi.gov.vn/) | `hanoi.gov.vn`, `www.hanoi.gov.vn` | Thông tin chính quyền địa phương và thông báo công cộng |
| [Cổng thông tin Hải Phòng](https://haiphong.gov.vn/) | `haiphong.gov.vn`, `www.haiphong.gov.vn` | Thông tin chính quyền địa phương và thông báo công cộng |
| [Cổng thông tin Nghệ An](https://nghean.gov.vn/) | `nghean.gov.vn`, `www.nghean.gov.vn` | Thông tin chính quyền địa phương và thông báo công cộng |
| [Cổng thông tin Quốc hội](https://quochoi.vn/vanphongquochoi/gioithieu/pages/don-vi.aspx?ItemID=61) | `quochoi.vn` | Chương trình kỳ họp, dự án luật và nghị quyết |
| [Cổng thông tin Thanh Hóa](https://thanhhoa.gov.vn/) | `thanhhoa.gov.vn` | Thông tin chính quyền địa phương và thông báo công cộng |
| [Cổng thông tin Thành phố Hồ Chí Minh](https://hochiminhcity.gov.vn/) | `hochiminhcity.gov.vn`, `www.hochiminhcity.gov.vn` | Thông tin chính quyền địa phương và thông báo công cộng |
| [Cổng Thông tin điện tử Chính phủ](https://chinhphu.vn/) | `chinhphu.vn`, `www.chinhphu.vn` | Thông tin điều hành và văn bản chính thức |
| [Cổng thông tin Đà Nẵng](https://danang.gov.vn/) | `danang.gov.vn` | Thông tin chính quyền địa phương và thông báo công cộng |
| [Cổng thông tin Đảng Cộng sản Việt Nam](https://dangcongsan.vn/) | `dangcongsan.vn` | Thông tin chính trị, chính sách; kiểm bài gốc |
| [Cổng thông tin Đồng Nai](https://dongnai.gov.vn/) | `dongnai.gov.vn`, `www.dongnai.gov.vn` | Thông tin chính quyền địa phương và thông báo công cộng |
| [Cục Quản lý Dược](https://dav.gov.vn/) | `dav.gov.vn`, `www.dav.gov.vn` | Thu hồi thuốc, cấp phép và thông báo dược |
| [Cục Thống kê](https://nso.gov.vn/) | `nso.gov.vn`, `www.nso.gov.vn` | Số liệu thống kê; kiểm kỳ báo cáo và đơn vị |
| [NASA](https://www.nasa.gov/) | `www.nasa.gov` | Không gian và khoa học do NASA công bố |
| [NASA Science](https://science.nasa.gov/) | `science.nasa.gov`, `www.science.nasa.gov` | Kết quả khoa học và dữ liệu NASA |
| [Ngân hàng Nhà nước Việt Nam](https://www.sbv.gov.vn/) | `sbv.gov.vn`, `www.sbv.gov.vn` | Tỷ giá, lãi suất, chính sách tiền tệ |
| [Thanh tra Chính phủ](https://thanhtra.gov.vn/) | `thanhtra.gov.vn` | Kết luận và thông tin thanh tra được công bố |
| [Trang tin Đảng bộ Thành phố Hồ Chí Minh](https://hcmcpv.org.vn/) | `hcmcpv.org.vn`, `www.hcmcpv.org.vn` | Thông tin thuộc cơ quan Đảng bộ thành phố |
| [Trung tâm Dự báo Khí tượng Thủy văn Quốc gia](https://nchmf.gov.vn/) | `nchmf.gov.vn`, `www.nchmf.gov.vn` | Bản tin khí tượng thủy văn có ngày phát hành |
| [Trung tâm Internet Việt Nam](https://vnnic.vn/) | `vnnic.vn`, `www.vnnic.vn` | Tên miền và số liệu Internet do đơn vị công bố |
| [Viện kiểm sát nhân dân tối cao](https://vksndtc.gov.vn/) | `vksndtc.gov.vn` | Thông tin tư pháp thuộc chức năng cơ quan |
| [Văn bản Chính phủ](https://vanban.chinhphu.vn/) | `vanban.chinhphu.vn` | Văn bản quy phạm pháp luật; đối chiếu số hiệu và hiệu lực |
| [Văn phòng Chính phủ](https://vpcp.chinhphu.vn/) | `vpcp.chinhphu.vn` | Thông cáo và hoạt động Văn phòng Chính phủ |
| [Xây dựng chính sách pháp luật](https://xaydungchinhsach.chinhphu.vn/) | `xaydungchinhsach.chinhphu.vn` | Chính sách pháp luật; phân biệt dự thảo với văn bản đã ban hành |

### Báo, đài và tạp chí

| Cơ quan/ấn phẩm | Hostname | Phạm vi |
| --- | --- | --- |
| [BNEWS - Thông tấn xã Việt Nam](https://bnews.vn/) | `bnews.vn` | Tin kinh tế TTXVN; kiểm nguồn và thời điểm |
| [Báo An Giang](https://baoangiang.com.vn/) | `baoangiang.com.vn`, `www.baoangiang.com.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Cao Bằng](https://baocaobang.vn/) | `baocaobang.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Cà Mau](https://baocamau.vn/) | `baocamau.vn`, `www.baocamau.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Công an nhân dân](https://cand.com.vn/) | `cand.com.vn`, `www.cand.com.vn`, `cand.vn` | Tin thời sự, pháp luật và an ninh; kiểm bài gốc |
| [Báo Công lý](https://congly.vn/) | `congly.vn`, `www.congly.vn` | Tin pháp luật, Quốc hội và thời sự; kiểm tác giả, ngày đăng và nội dung gốc |
| [Báo Công Thương](https://congthuong.vn/) | `congthuong.vn`, `www.congthuong.vn` | Điều hành giá xăng dầu, thương mại; kiểm tác giả/thời gian/nguồn |
| [Báo Cần Thơ](https://baocantho.com.vn/) | `baocantho.com.vn`, `www.baocantho.com.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Gia Lai](https://baogialai.com.vn/) | `baogialai.com.vn`, `www.baogialai.com.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Giao thông](https://baogiaothong.vn/) | `baogiaothong.vn`, `www.baogiaothong.vn` | Tin giao thông; kiểm chuyển hướng sang cơ quan hiện hành |
| [Báo Giáo dục và Thời đại](https://giaoducthoidai.vn/) | `giaoducthoidai.vn`, `www.giaoducthoidai.vn` | Giáo dục, tuyển sinh và chính sách; kiểm bài gốc |
| [Báo Hà Nội Mới](https://hanoimoi.vn/) | `hanoimoi.vn`, `www.hanoimoi.vn` | Tin Hà Nội và thời sự; kiểm bài gốc |
| [Báo Hưng Yên](https://baohungyen.vn/) | `baohungyen.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Hải Phòng](https://baohaiphong.vn/) | `baohaiphong.vn`, `www.baohaiphong.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Khánh Hòa](https://baokhanhhoa.vn/) | `baokhanhhoa.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Lai Châu](https://baolaichau.vn/) | `baolaichau.vn`, `www.baolaichau.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Lào Cai](https://baolaocai.vn/) | `baolaocai.vn`, `www.baolaocai.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Lâm Đồng](https://baolamdong.vn/) | `baolamdong.vn`, `www.baolamdong.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Lạng Sơn](https://baolangson.vn/) | `baolangson.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Nghệ An](https://baonghean.vn/) | `baonghean.vn`, `www.baonghean.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Nhân Dân](https://nhandan.vn/) | `nhandan.vn`, `www.nhandan.vn` | Cơ quan báo chí; tin chính thống |
| [Báo Nhân Dân - địa chỉ lưu trữ](https://nhandan.org.vn/) | `nhandan.org.vn`, `www.nhandan.org.vn` | Tin báo chí và bài lưu trữ; ưu tiên địa chỉ hiện hành |
| [Báo Ninh Bình](https://baoninhbinh.org.vn/) | `baoninhbinh.org.vn`, `www.baoninhbinh.org.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Pháp luật Việt Nam](https://baophapluat.vn/) | `baophapluat.vn`, `www.baophapluat.vn` | Tin pháp luật, tư pháp và thời sự |
| [Báo Phú Thọ](https://baophutho.vn/) | `baophutho.vn`, `www.baophutho.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Quân đội nhân dân](https://www.qdnd.vn/quoc-phong-an-ninh/tin-tuc/quan-uy-trung-uong-to-chuc-hoi-nghi-lan-thu-muoi-hai-thong-qua-cac-noi-dung-quan-trong-807209) | `qdnd.vn`, `www.qdnd.vn` | Tin thời sự và quốc phòng; kiểm ngày và nội dung gốc |
| [Báo Quảng Ngãi](https://baoquangngai.vn/) | `baoquangngai.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Quảng Ninh](https://baoquangninh.vn/) | `baoquangninh.vn`, `www.baoquangninh.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Quảng Trị](https://baoquangtri.vn/) | `baoquangtri.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Sức khỏe và Đời sống](https://suckhoedoisong.vn/) | `suckhoedoisong.vn`, `www.suckhoedoisong.vn` | Thông tin y tế; đối chiếu hướng dẫn và nghiên cứu gốc |
| [Báo Thanh Hóa](https://baothanhhoa.vn/) | `baothanhhoa.vn`, `www.baothanhhoa.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Thái Nguyên](https://baothainguyen.vn/) | `baothainguyen.vn`, `www.baothainguyen.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Tin Tức (TTXVN)](https://baotintuc.vn/) | `baotintuc.vn`, `www.baotintuc.vn` | Tin chính thống TTXVN; kiểm tác giả/thời gian/nguồn |
| [Báo Tuyên Quang](https://baotuyenquang.com.vn/) | `baotuyenquang.com.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Tây Ninh](https://baotayninh.vn/) | `baotayninh.vn`, `www.baotayninh.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Văn Hóa](https://baovanhoa.vn/) | `baovanhoa.vn`, `www.baovanhoa.vn` | Tin văn hóa, xã hội, kinh tế và công nghệ; kiểm nội dung gốc và ngày đăng |
| [Báo Vĩnh Long](https://baovinhlong.com.vn/) | `baovinhlong.com.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Xây dựng](https://baoxaydung.vn/) | `baoxaydung.vn`, `www.baoxaydung.vn` | Hạ tầng, giao thông và xây dựng |
| [Báo Đà Nẵng](https://baodanang.vn/) | `baodanang.vn`, `www.baodanang.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Đại biểu Nhân dân](https://daibieunhandan.vn/) | `daibieunhandan.vn`, `www.daibieunhandan.vn` | Quốc hội và chính sách; kiểm dự thảo, thời điểm |
| [Báo Đầu Tư](https://baodautu.vn/) | `baodautu.vn`, `www.baodautu.vn` | Kinh tế, đầu tư, tài chính; kiểm tác giả/thời gian/nguồn |
| [Báo Đắk Lắk](https://baodaklak.vn/) | `baodaklak.vn`, `www.baodaklak.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Đồng Nai](https://baodongnai.com.vn/) | `baodongnai.com.vn`, `www.baodongnai.com.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Báo Đồng Tháp](https://baodongthap.vn/) | `baodongthap.vn`, `www.baodongthap.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [CafeF](https://cafef.vn/) | `cafef.vn`, `www.cafef.vn` | Kinh tế, tài chính, thị trường; kiểm tác giả/thời gian/nguồn |
| [CNA](https://www.channelnewsasia.com/) | `www.channelnewsasia.com` | Tin khu vực và quốc tế; kiểm bài gốc |
| [Dân Trí](https://dantri.com.vn/) | `dantri.com.vn`, `www.dantri.com.vn` | Tin tức tổng hợp; kiểm tác giả/thời gian/nguồn |
| [Dân tộc và Miền núi - TTXVN](https://dantocmiennui.baotintuc.vn/) | `dantocmiennui.baotintuc.vn` | Thông tin dân tộc và miền núi; kiểm bài gốc |
| [France 24](https://www.france24.com/) | `www.france24.com` | Tin quốc tế; kiểm bài gốc và thời điểm |
| [Huế ngày nay](https://huengaynay.vn/) | `huengaynay.vn`, `www.huengaynay.vn` | Tin địa phương và thời sự; kiểm ngày và nội dung gốc |
| [Kinh tế & Đô thị](https://kinhtedothi.vn/) | `kinhtedothi.vn` | Kinh tế, đô thị, tin tổng hợp; kiểm tác giả/thời gian/nguồn |
| [Lao Động](https://laodong.vn/) | `laodong.vn` | Tin tức tổng hợp; kiểm tác giả/thời gian/nguồn |
| [Người Lao Động](https://nld.com.vn/) | `nld.com.vn`, `www.nld.com.vn` | Tin tức tổng hợp; kiểm tác giả/thời gian/nguồn |
| [NHK](https://www.nhk.or.jp/) | `www.nhk.or.jp` | Tin Nhật Bản và quốc tế; kiểm bài gốc |
| [Pháp Luật TP.HCM](https://plo.vn/) | `plo.vn` | Tin tức tổng hợp, pháp luật; kiểm tác giả/thời gian/nguồn |
| [Sài Gòn Giải Phóng](https://www.sggp.org.vn/) | `sggp.org.vn`, `www.sggp.org.vn` | Tin tức tổng hợp; kiểm tác giả/thời gian/nguồn |
| [Thanh Niên](https://thanhnien.vn/) | `thanhnien.vn`, `www.thanhnien.vn` | Tin tức tổng hợp; kiểm tác giả/thời gian/nguồn |
| [Thông tấn xã Việt Nam](https://vnanet.vn/) | `vnanet.vn`, `www.vnanet.vn` | Thông tấn nhà nước; tin thời sự, chính sách và dữ liệu công bố |
| [Thời báo Ngân hàng](https://thoibaonganhang.vn/) | `thoibaonganhang.vn` | Chính sách tiền tệ và ngân hàng; kiểm số liệu gốc |
| [Thời báo Tài chính Việt Nam](https://thoibaotaichinhvietnam.vn/) | `thoibaotaichinhvietnam.vn`, `www.thoibaotaichinhvietnam.vn` | Tài chính, thuế, giá (cơ quan của Bộ Tài chính); kiểm tác giả/thời gian/nguồn |
| [Tiền Phong](https://tienphong.vn/) | `tienphong.vn`, `www.tienphong.vn` | Tin tức tổng hợp; kiểm tác giả/thời gian/nguồn |
| [Tuổi Trẻ](https://tuoitre.vn/) | `tuoitre.vn`, `www.tuoitre.vn` | Tin tức tổng hợp; kiểm tác giả/thời gian/nguồn |
| [Tạp chí Diễn đàn Doanh nghiệp](https://diendandoanhnghiep.vn/) | `diendandoanhnghiep.vn`, `www.diendandoanhnghiep.vn` | Kinh tế và doanh nghiệp; phân biệt tin, ý kiến và quảng cáo |
| [Tạp chí Kinh doanh](https://vnbusiness.vn/) | `vnbusiness.vn`, `www.vnbusiness.vn` | Kinh doanh và hợp tác xã; kiểm bài gốc |
| [Tạp chí Tòa án nhân dân](https://tapchitoaan.vn/) | `tapchitoaan.vn`, `www.tapchitoaan.vn` | Nghiên cứu, bình luận pháp luật; phân biệt ý kiến với quy định có hiệu lực |
| [Tạp chí VietnamFinance](https://vietnamfinance.vn/) | `vietnamfinance.vn`, `www.vietnamfinance.vn` | Kinh tế và tài chính; kiểm số liệu và nguồn gốc |
| [Viet Nam News - TTXVN](https://vietnamnews.vn/) | `vietnamnews.vn`, `www.vietnamnews.vn` | Tin Việt Nam bằng tiếng Anh; kiểm nội dung và ngày |
| [Vietnam Today - VTV](https://vietnamtoday.vtv.vn/) | `vietnamtoday.vtv.vn` | Tin đối ngoại của VTV; kiểm bài gốc |
| [VietNamNet](https://vietnamnet.vn/) | `vietnamnet.vn`, `www.vietnamnet.vn` | Tin tức tổng hợp; kiểm tác giả/thời gian/nguồn |
| [VietnamPlus (TTXVN)](https://www.vietnamplus.vn/) | `vietnamplus.vn`, `www.vietnamplus.vn` | Tin chính thống TTXVN; kiểm tác giả/thời gian/nguồn |
| [VnEconomy](https://vneconomy.vn/) | `vneconomy.vn`, `www.vneconomy.vn` | Kinh tế, tài chính, giá cả; kiểm tác giả/thời gian/nguồn |
| [VnExpress](https://vnexpress.net/) | `vnexpress.net`, `www.vnexpress.net` | Tin tức tổng hợp; cần kiểm tra tác giả, thời gian và nguồn gốc |
| [VOV Giao thông](https://vovgiaothong.vn/) | `vovgiaothong.vn`, `www.vovgiaothong.vn` | Tin giao thông và đô thị; kiểm bài gốc |
| [VOV World](https://vovworld.vn/) | `vovworld.vn` | Tin đối ngoại của VOV; kiểm ngôn ngữ và bài gốc |
| [VTC News](https://vtcnews.vn/) | `vtcnews.vn` | Tin tức tổng hợp; kiểm tác giả/thời gian/nguồn |
| [Đài Hà Nội](https://hanoionline.vn/) | `hanoionline.vn` | Tin Hà Nội và chương trình phát thanh truyền hình |
| [Đài Tiếng nói Việt Nam](https://vov.vn/) | `vov.vn` | Tin thời sự và chương trình phát thanh của cơ quan báo chí quốc gia |
| [Đài Truyền hình Việt Nam](https://vtv.vn/) | `vtv.vn`, `www.vtv.vn` | Tin tức tổng hợp; kiểm tác giả/thời gian/nguồn |

### Tổ chức quốc tế và khoa học

| Cơ quan/ấn phẩm | Hostname | Phạm vi |
| --- | --- | --- |
| [CERN](https://home.cern/) | `home.cern`, `www.home.cern` | Vật lý hạt và công bố của CERN |
| [Cơ quan Vũ trụ châu Âu](https://www.esa.int/) | `www.esa.int` | Nghiên cứu không gian và thông cáo ESA |
| [Dữ liệu Ngân hàng Thế giới](https://data.worldbank.org/) | `data.worldbank.org` | Dữ liệu thống kê; kiểm định nghĩa chỉ tiêu và kỳ |
| [FAO](https://www.fao.org/) | `www.fao.org` | Nông nghiệp, lương thực và số liệu FAO |
| [ILO](https://www.ilo.org/) | `www.ilo.org` | Lao động và dữ liệu do ILO công bố |
| [IPCC](https://www.ipcc.ch/about/structure/) | `www.ipcc.ch` | Báo cáo đánh giá khí hậu; kiểm phiên bản báo cáo |
| [Liên Hợp Quốc](https://www.un.org/) | `www.un.org` | Thông cáo và dữ liệu do Liên Hợp Quốc công bố |
| [Ngân hàng Phát triển châu Á](https://www.adb.org/who-we-are) | `www.adb.org` | Dữ liệu và báo cáo ADB |
| [Ngân hàng Thế giới](https://www.worldbank.org/) | `www.worldbank.org` | Dữ liệu và báo cáo Ngân hàng Thế giới; kiểm kỳ và đơn vị |
| [OECD](https://www.oecd.org/en/about.html) | `www.oecd.org` | Báo cáo, dữ liệu và phương pháp thống kê OECD |
| [Quỹ Tiền tệ Quốc tế](https://www.imf.org/en/about) | `www.imf.org` | Dữ liệu, dự báo và báo cáo IMF; phân biệt dự báo với thực tế |
| [Tổ chức Khí tượng Thế giới](https://wmo.int/) | `wmo.int`, `www.wmo.int` | Khí tượng và báo cáo WMO |
| [Tổ chức Thương mại Thế giới](https://www.wto.org/) | `www.wto.org` | Thương mại và công bố WTO |
| [UN News](https://news.un.org/) | `news.un.org` | Tin tức của Liên Hợp Quốc; kiểm cơ quan phát ngôn và ngày |
| [UNDP](https://www.undp.org/about-us) | `www.undp.org` | Phát triển và báo cáo do UNDP công bố |
| [UNESCO](https://www.unesco.org/) | `www.unesco.org` | Giáo dục, khoa học, văn hóa và công bố UNESCO |
| [UNICEF](https://www.unicef.org/) | `www.unicef.org` | Dữ liệu trẻ em và thông tin do UNICEF công bố |
| [World Health Organization](https://www.who.int/vietnam) | `www.who.int` | Y tế và sức khỏe cộng đồng |

### Nguồn công bố trực tiếp của doanh nghiệp

| Cơ quan/ấn phẩm | Hostname | Phạm vi |
| --- | --- | --- |
| [Apple Newsroom](https://www.apple.com/) | `www.apple.com` | Chỉ xác nhận công bố và sản phẩm Apple |
| [Công ty Vàng bạc Đá quý Sài Gòn (SJC)](https://sjc.com.vn/) | `sjc.com.vn`, `www.sjc.com.vn` | Giá vàng do SJC công bố; yêu cầu mốc cập nhật trên nguồn |
| [Google Blog](https://blog.google/) | `blog.google`, `www.blog.google` | Chỉ xác nhận công bố và sản phẩm Google |
| [Microsoft News](https://news.microsoft.com/) | `news.microsoft.com` | Chỉ xác nhận thông cáo của Microsoft |
| [Ngân hàng Vietcombank](https://vietcombank.com.vn/) | `vietcombank.com.vn`, `www.vietcombank.com.vn` | Tỷ giá và lãi suất do Vietcombank công bố; yêu cầu ngày cập nhật |
| [NVIDIA Newsroom](https://nvidianews.nvidia.com/) | `nvidianews.nvidia.com` | Chỉ xác nhận sản phẩm và công bố NVIDIA |
| [Samsung Newsroom](https://news.samsung.com/) | `news.samsung.com` | Chỉ xác nhận thông cáo, sản phẩm và công bố của Samsung |
| [Samsung Newsroom và công bố doanh nghiệp](https://www.samsung.com/) | `www.samsung.com` | Chỉ xác nhận sản phẩm và công bố của Samsung; không đánh giá khách quan thị trường |
| [Sở Giao dịch Chứng khoán Thành phố Hồ Chí Minh](https://www.hsx.vn/) | `www.hsx.vn` | Thông báo sở giao dịch và công bố tổ chức niêm yết |
| [TSMC](https://www.tsmc.com/) | `www.tsmc.com` | Chỉ xác nhận công bố doanh nghiệp, công nghệ và báo cáo TSMC |
| [TSMC Newsroom](https://pr.tsmc.com/) | `pr.tsmc.com` | Chỉ xác nhận thông cáo và công bố TSMC |
| [Tập đoàn Xăng dầu Việt Nam (Petrolimex)](https://petrolimex.com.vn/) | `petrolimex.com.vn`, `www.petrolimex.com.vn` | Thông cáo giá bán lẻ xăng dầu của Petrolimex; chỉ xác nhận giá do doanh nghiệp công bố |
| [Tập đoàn Điện lực Việt Nam (EVN)](https://evn.com.vn/) | `evn.com.vn`, `www.evn.com.vn` | Thông cáo giá điện và thông tin do EVN công bố |

## Nạp cấu hình mới

Dừng phiên Gradio cũ bằng Ctrl+C trong terminal của ứng dụng rồi chạy lại:

```powershell
.\.venv312\Scripts\python.exe app_gradio.py --no-browser
```

Ứng dụng chọn cổng trống nếu không truyền `--port`. Danh mục nguồn mới không
yêu cầu nhập URL bài gốc; UI tiếp tục chỉ nhận phát biểu và tùy chọn kiểm chứng.
