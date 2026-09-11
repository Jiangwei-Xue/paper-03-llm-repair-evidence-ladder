$pdf_mode = 1;
$pdflatex = 'pdflatex -interaction=nonstopmode -halt-on-error -file-line-error %O %S';
my $bibtex_cmd = -x '/usr/bin/bibtex.original' ? '/usr/bin/bibtex.original' : 'bibtex';
$bibtex = "$bibtex_cmd %O %B";
$out_dir = 'build';
