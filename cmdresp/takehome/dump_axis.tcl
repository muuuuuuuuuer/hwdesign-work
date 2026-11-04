# Run in the directory of the generated XSim snapshot.
# Set FIR_DUT_SCOPE to its slash-delimited DUT scope if discovery finds no match.
if {[info exists ::env(FIR_DUT_SCOPE)]} {
    set dut $::env(FIR_DUT_SCOPE)
} else {
    set scopes [get_scopes -r *AESL_inst_fir4]
    if {[llength $scopes] != 1} {
        error "Set FIR_DUT_SCOPE to the FIR instance path from the XSim hierarchy."
    }
    set dut [lindex $scopes 0]
}
set ports [get_objects -filter {type == port} "${dut}/*"]
if {[llength $ports] == 0} {
    error "No top-level FIR ports found at $dut."
}
open_vcd fir4_axis.vcd
log_vcd $ports
run all
close_vcd
quit
