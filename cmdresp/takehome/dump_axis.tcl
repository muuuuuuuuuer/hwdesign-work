# Run after the dedicated timing co-simulation, in its sim/verilog directory.
set dut /apatb_fir4_top/AESL_inst_fir4
if {[info exists ::env(FIR_DUT_SCOPE)]} { set dut $::env(FIR_DUT_SCOPE) }
open_vcd fir4_axis.vcd
foreach signal {ap_clk in_stream_TDATA in_stream_TLAST in_stream_TVALID in_stream_TREADY out_stream_TDATA out_stream_TLAST out_stream_TVALID out_stream_TREADY} {
    log_vcd ${dut}/${signal}
}
run all
close_vcd
quit
